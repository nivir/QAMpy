import numpy as np
import matplotlib.pylab as plt
from dsp import equalisation, signals, impairments, helpers, phaserec

fb = 40.e9
os = 2
fs = os*fb
N = 10**5
mu = 4e-4
theta = np.pi/5.45
theta2 = np.pi/4
t_pmd = 75e-12
M = 4
ntaps=40
snr =  14

sig = signals.SignalQAMGrayCoded(M, N, fb=fb, nmodes=2)
S = sig.resample(fs, renormalise=True, beta=0.1)
S = impairments.apply_phase_noise(S, 100e3)
S = impairments.change_snr(S, snr)

SS = impairments.apply_PMD_to_field(S, theta, t_pmd)
wxy, err = equalisation.equalise_signal(SS, mu, Ntaps=ntaps, Trsyms=10, method="mcma", adaptive_step=True)
wxy_m, err_m = equalisation.equalise_signal(SS.astype(np.complex64), mu,  Trsyms=10,Ntaps=ntaps, method="mcma", adaptive_step=True)
E = equalisation.apply_filter(SS,  wxy)
E_m = equalisation.apply_filter(SS, wxy_m)
E = helpers.normalise_and_center(E)
E_m = helpers.normalise_and_center(E_m)
E, ph = phaserec.viterbiviterbi(E, 11)
E_m, ph = phaserec.viterbiviterbi(E_m, 11)
E = helpers.dump_edges(E, 20)
E_m = helpers.dump_edges(E_m, 20)


# note that because of the noise we get sync failures doing SER
ser = E.cal_ser()
ser_m = E_m.cal_ser()
ser0 = S[:, ::2].cal_ser()
plt.figure()
plt.subplot(131)
plt.title('Recovered CMA')
plt.plot(E[0].real, E[0].imag, 'ro', label=r"$SER_x=%.1f\%%$"%(100*ser[0]))
plt.plot(E[1].real, E[1].imag, 'go' ,label=r"$SER=%.1f\%%$"%(ser[1]*100))
plt.legend()
plt.subplot(132)
plt.title('Recovered MCMA')
plt.plot(E_m[0].real, E_m[0].imag, 'ro', label=r"$SER_x=%.1f\%%$"%(100*ser_m[0]))
plt.plot(E_m[1].real, E_m[1].imag, 'go' ,label=r"$SER_y=%.1f\%%$"%(ser_m[1]*100))
plt.legend()
plt.subplot(133)
plt.title('Original')
plt.plot(S[0,::2].real, S[0,::2].imag, 'ro', label=r"$SER_x=%.1f\%%$"%(100*ser0[0]))
plt.plot(S[1,::2].real, S[1,::2].imag, 'go', label=r"$SER_y=%.1f\%%$"%(100*ser0[1]))
plt.legend()

plt.figure()
plt.subplot(221)
plt.title('Taps CMA')
plt.plot(wxy[0][0,:], 'r')
plt.plot(wxy[0][1,:], '--r')
plt.plot(wxy[1][0,:], 'g')
plt.plot(wxy[1][1,:], '--g')
plt.subplot(222)
plt.title('error CMA')
plt.plot(abs(err[0]), color='r')
plt.plot(abs(err[1]), color='g')
plt.subplot(223)
plt.title('Taps MCMA')
plt.plot(wxy_m[0][0,:], 'r')
plt.plot(wxy_m[0][1,:], '--r')
plt.plot(wxy_m[1][0,:], 'g')
plt.plot(wxy_m[1][1,:], '--g')
plt.subplot(224)
plt.title('error MCMA')
plt.plot(abs(err_m[0]), color='r')
plt.plot(abs(err_m[1]), color='g')
plt.show()



