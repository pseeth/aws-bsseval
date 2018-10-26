import numpy as np
# This variant of BSSEval measures is scale-invariant. Used for speech separation papers.


def get_sdr_no_perm_speech(estimated_signals, reference_signals, scaling=True):
    """
    """
    num_samples = estimated_signals.shape[0]
    T, C = reference_signals.shape

    if T != num_samples:
        raise ValueError('The estimated sources and reference sources must have the same duration.')

    estimated_signals = estimated_signals - estimated_signals.mean(axis=0)
    reference_signals = reference_signals - reference_signals.mean(axis=0)

    # Performance citeria

    SDR, SIR, SAR = compute_measures(estimated_signals, reference_signals, 0, scaling=scaling)

    return SDR, SIR, SAR


def compute_measures(estimated_signal, reference_signals, j, scaling=True):
    Rss = np.dot(reference_signals.transpose(), reference_signals)
    this_s = reference_signals[:, j]

    if scaling:
        # get the scaling factor for clean sources
        a = np.dot(this_s, estimated_signal) / Rss[j, j]
    else:
        a = 1

    e_true = a * this_s
    e_res = estimated_signal - e_true

    Sss = (e_true ** 2).sum()
    Snn = (e_res ** 2).sum()

    SDR = 10 * np.log10(Sss / Snn)

    # Get the SIR
    Rsr = np.dot(reference_signals.transpose(), e_res)
    b = np.linalg.solve(Rss, Rsr)

    e_interf = np.dot(reference_signals, b)
    e_artif = e_res - e_interf

    SIR = 10 * np.log10(Sss / (e_interf ** 2).sum())
    SAR = 10 * np.log10(Sss / (e_artif ** 2).sum())

    return SDR, SIR, SAR


# Time domain signals
if __name__ == '__main__':
    mix_sig = np.random.rand(10 * 8000)s
    estimated_sig = np.random.rand(10 * 8000)
    reference_sig = np.random.rand(10 * 8000)
    residual_sig = mix_sig - reference_sig

    sdr, sir, sar = get_sdr_no_perm_speech(estimated_sig, np.stack([reference_sig, residual_sig]).T)
    print(sdr, sir, sar)