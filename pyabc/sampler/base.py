from abc import ABC, ABCMeta, abstractmethod
import numpy as np
from numbers import Real
from typing import Callable, Union

from ..population import Sample, SampleFactory
from ..util import AnalysisVars
from ..distance import Distance
from ..epsilon import Epsilon
from ..acceptor import Acceptor


def wrap_sample(f):
    """Wrapper for Sampler.sample_until_n_accepted.
    Checks whether the sampling output is valid.
    """
    def sample_until_n_accepted(self, n, simulate_one, t, **kwargs):
        sample = f(self, n, simulate_one, t, **kwargs)

        if sample.n_accepted != n and sample.ok:
            # this should not happen if the sampler is configured correctly
            raise AssertionError(
                f"Expected {n} but got {sample.n_accepted} acceptances.")

        if any(particle.preliminary for particle in sample.all_particles):
            raise AssertionError(
                "There cannot be non-evaluated particles.")
        # normalize sample weights
        sample.normalize_weights()

        return sample
    return sample_until_n_accepted


class SamplerMeta(ABCMeta):
    """
    This metaclass handles the checking of sampling output values.
    """

    def __init__(cls, name, bases, attrs):
        ABCMeta.__init__(cls, name, bases, attrs)
        cls.sample_until_n_accepted = wrap_sample(cls.sample_until_n_accepted)


class Sampler(ABC, metaclass=SamplerMeta):
    """
    Abstract Sampler base class.

    Produce valid particles: :class:`pyabc.parameters.ValidParticle`.

    Attributes
    ----------
    nr_evaluations_: int
        This is set after a population and counts the total number
        of model evaluations. This can be used to calculate the acceptance
        rate.
    sample_factory: SampleFactory
        A factory to create empty samples.
    show_progress: bool
        Whether to show progress within a generation.
        Some samplers support this by e.g. showing a progress bar.
        Set via
        >>> sampler = Sampler()
        >>> sampler.show_progress = True
    analysis_id: str
        A universal unique id of the analysis, automatically generated by the
        inference routine.
    """

    def __init__(self):
        self.nr_evaluations_: int = 0
        self.sample_factory: SampleFactory = \
            SampleFactory(record_rejected=False)
        self.show_progress: bool = False
        self.analysis_id: Union[str, None] = None

    def _create_empty_sample(self) -> Sample:
        return self.sample_factory()

    def set_analysis_id(self, analysis_id: str):
        """Set the analysis id.
        Called by the inference routine.
        The default is to just obediently set it. Specific samplers may want to
        check whether there are conflicting analyses.
        """
        self.analysis_id = analysis_id

    @abstractmethod
    def sample_until_n_accepted(
        self,
        n: int,
        simulate_one: Callable,
        t: int,
        *,
        max_eval: Real = np.inf,
        all_accepted: bool = False,
        ana_vars: AnalysisVars = None,
    ) -> Sample:
        """
        Performs the sampling, i.e. creation of a new generation (i.e.
        population) of particles.

        Parameters
        ----------
        n:
            The number of samples to be accepted. I.e. the population size.
        simulate_one:
            A function which internally performs the whole process of
            sampling parameters, simulating data, and comparing to observed
            data to check for acceptance, as indicated via the
            particle.accepted flag.
        t:
            Generation index for which to sample.
        max_eval:
            Maximum number of evaluations to perform. Some samplers can check
            this condition directly and can thus terminate proactively.
        all_accepted:
            If it is known in advance that all sampled particles will have
            particle.accepted == True, then setting all_accepted = True can
            reduce the computational overhead for dynamic schedulers. This
            is usually in particular the case in the initial calibration
            iteration.
        ana_vars:
            Various analysis variables. Some samplers can use these e.g. for
            proactive sampling.

        Returns
        -------
        sample: :class:`pyabc.sampler.Sample`
            The generated sample, which contains the new population.
        """

    def stop(self) -> None:
        """Stop the sampler.
        Called by the inference routine when an analysis is finished.
        Some samplers may need to e.g. finish ongoing processes or close
        servers.
        """

    def check_analysis_variables(
            self,
            distance_function: Distance,
            eps: Epsilon,
            acceptor: Acceptor) -> None:
        """Raise if any analysis variable is not conform with the sampler.
        This check serves in particular to ensure that all components are fit
        for look-ahead sampling. Default: Do nothing.
        """
