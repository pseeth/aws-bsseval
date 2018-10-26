import numpy as np
from itertools import permutations
# This variant of BSSEval measures is scale-invariant. Used for speech separation papers.


def get_sdr_noperm_speech(estimated_signals, reference_signals, scaling=True):
    """
    """
    num_samples = estimated_signals.shape[0]
    T, C = reference_signals.shape

    if T != num_samples:
        raise ValueError('The estimated sources and reference sources must have the same duration.')

    estimated_signals= estimated_signals - estimated_signals.mean(axis=0)
    reference_signals= reference_signals - reference_signals.mean(axis=0)

    # Performance citeria

    SDR, SIR, SAR = compute_measures(estimated_signals, reference_signals, 0, scaling=scaling)


    return SDR, SIR, SAR


def compute_measures(estimated_signal, reference_signals, j, scaling=True):

    Rss= np.dot(reference_signals.transpose(), reference_signals)
    this_s= reference_signals[:,j]

    if scaling:
        # get the scaling factor for clean sources
        a = np.dot( this_s, estimated_signal) / Rss[j,j]
    else:
        a = 1

    e_true = a * this_s
    e_res = estimated_signal - e_true

    Sss = (e_true**2).sum()
    Snn = (e_res**2).sum()

    SDR = 10 * np.log10(Sss/Snn)

    # Get the SIR
    Rsr = np.dot(reference_signals.transpose(), e_res)
    b = np.linalg.solve(Rss, Rsr)

    e_interf = np.dot(reference_signals , b)
    e_artif = e_res - e_interf
    
    SIR = 10 * np.log10(Sss / (e_interf**2).sum())
    SAR = 10 * np.log10(Sss / (e_artif**2).sum())

    return SDR, SIR,SAR


def sdr_permutation_search(mix_sig, src_sigs, est_sigs):
    n_srcs = len(src_sigs)
    perms = []
    all_outputs = []
    for perm in permutations(range(n_srcs)):
        outputs = []
        for k, src_sig in zip(perm, src_sigs):
            res_sig = mix_sig - src_sig
            metrics = get_sdr_noperm_speech(est_sigs[k], np.stack([src_sig, res_sig]).T)
            outputs.append(metrics)
        perms.append(np.asarray(outputs).mean(0))
        all_outputs.append(outputs)
    best_perm = np.asarray(perms)[:,0].argmax()
    return np.asarray(all_outputs)[best_perm,:,:]


if __name__ == '__main__':
    # Time domain signals
    s_len = 5000
    mix_sig = np.random.rand(s_len)
    estimated_sigs = [np.random.rand(s_len), np.random.rand(s_len)] 
    reference_sigs = [np.random.rand(s_len), np.random.rand(s_len)]
    metrics = sdr_permutation_search(mix_sig, reference_sigs, estimated_sigs)
    print(metrics)