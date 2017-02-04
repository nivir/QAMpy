# cython: profile=True, boundscheck=False, wraparound=False
from __future__ import division
import numpy as np
from cython.view cimport array as cvarray
from cython.parallel import prange
cimport cython
cimport numpy as np

cdef extern from "complex.h":
    double complex conj(double complex)

cdef extern from "equaliserC.h":
    double complex apply_filter(double complex *E, unsigned int Ntaps, double complex *wx, unsigned int pols, unsigned int L)

cdef extern from "equaliserC.h":
    double complex det_symbol(double complex *syms, unsigned int M, double complex value)

cdef extern from "equaliserC.h":
    void update_filter(double complex *E, unsigned int Ntaps, double mu, double complex err, double complex *wx, unsigned int pols, unsigned int L)


def partition_value(double signal,
                    np.ndarray[ndim=1, dtype=np.float64_t] partitions,
                    np.ndarray[ndim=1, dtype=np.float64_t] codebook):
    cdef unsigned int index = 0
    cdef unsigned int L = len(partitions)
    while index < L and signal > partitions[index]:
        index += 1
    return codebook[index]

cdef double adapt_step(double mu, double complex err_p, double complex err, int lm):
    if err.real*err_p.real > 0 and err.imag*err_p.imag >  0:
        lm = 0
    else:
        lm = 1
    mu = mu/(1+lm*mu*(err.real*err.real + err.imag*err.imag))
    return mu

def FS_CMA(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                    int TrSyms,
                    int Ntaps,
                    unsigned int os,
                    double mu,
                    np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                    double R):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    cdef np.complex128_t Xest
    for i in range(0, TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        err[<unsigned int> i] = Xest*(Xest.real**2+Xest.imag**2 - R)
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
    return err, wx

def MCMA_adaptive(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                  int TrSyms,
                  int Ntaps,
                  unsigned int os,
                  double mu,
                  np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                  np.complex128_t R):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    cdef np.complex128_t Xest
    for i in range(0, TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        err[<unsigned int> i] = (Xest.real**2 - R.real)*Xest.real + 1.j*(Xest.imag**2 - R.imag)*Xest.imag
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
        if i > 0:
            if err[<unsigned int> i].real*err[<unsigned int> i-1].real > 0 and err[<unsigned int> i].imag*err[<unsigned int> i-1].imag >  0:
                lm = 0
            else:
                lm = 1
                mu = mu/(1+lm*mu*(err[<unsigned int> i].real*err[<unsigned int> i].real + err[<unsigned int> i].imag*err[<unsigned int> i].imag))
    return err, wx

def FS_MCMA(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                     int TrSyms,
                     int Ntaps,
                     unsigned int os,
                     double mu,
                     np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                     np.complex128_t R):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    cdef np.complex128_t Xest
    for i in range(0, TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        err[<unsigned int> i] = (Xest.real**2 - R.real)*Xest.real + 1.j*(Xest.imag**2 - R.imag)*Xest.imag
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
    return err, wx

def FS_RDE(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                    int TrSyms,
                    int Ntaps,
                    unsigned int os,
                    double mu,
                    np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                    np.ndarray[ndim=1, dtype=np.float64_t] partition,
                    np.ndarray[ndim=1, dtype=np.float64_t] codebook):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    cdef double complex Xest
    cdef double Ssq, S_DD
    for i in range(TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        Ssq = Xest.real**2 + Xest.imag**2
        S_DD = partition_value(Ssq, partition, codebook)
        err[<unsigned int> i] = Xest*(Ssq - S_DD)
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
    return err, wx

def FS_MRDE(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                     int TrSyms, int Ntaps, unsigned int os,
                     double mu,
                     np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                     np.ndarray[ndim=1, dtype=np.complex128_t] partition,
                     np.ndarray[ndim=1, dtype=np.complex128_t] codebook):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    cdef np.complex128_t Xest, Ssq, S_DD
    for i in range(TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        Ssq = Xest.real**2 + 1.j * Xest.imag**2
        S_DD = partition_value(Ssq.real, partition.real, codebook.real) + 1.j * partition_value(Ssq.imag, partition.imag, codebook.imag)
        err[<unsigned int> i] = (Ssq.real - S_DD.real)*Xest.real + 1.j*(Ssq.imag - S_DD.imag)*Xest.imag
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
    return err, wx

def SBD(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                     int TrSyms, int Ntaps, unsigned int os,
                     double mu,
                     np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                     np.ndarray[ndim=1, dtype=np.complex128_t] symbols):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef unsigned int i, j, k, N
    cdef double complex Xest, R
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int M = len(symbols)
    cdef double lm
    cdef unsigned int L = E.shape[1]
    for i in range(TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        R = det_symbol(<double complex *>symbols.data, M, Xest)
        err[<unsigned int> i] = (Xest.real - R.real)*abs(R.real) + 1.j*(Xest.imag - R.imag)*abs(R.imag)
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
    return err, wx

def SBD_adaptive(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                     int TrSyms, int Ntaps, unsigned int os,
                     double mu,
                     np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                     np.ndarray[ndim=1, dtype=np.complex128_t] symbols):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k, N
    cdef np.complex128_t Xest, R
    cdef double lm
    cdef unsigned int M = len(symbols)
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    for i in range(TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        R = det_symbol(<double complex *>symbols.data, M, Xest)
        err[<unsigned int> i] = (Xest.real - R.real)*abs(R.real) + 1.j*(Xest.imag - R.imag)*abs(R.imag)
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
        if i > 0:
            if err[<unsigned int> i].real*err[<unsigned int> i-1].real > 0 and err[<unsigned int> i].imag*err[<unsigned int> i-1].imag >  0:
                lm = 0
            else:
                lm = 1
                #mu = mu/(1+lm*mu*(err[<unsigned int> i].real*err[<unsigned int> i].real + err[<unsigned int> i].imag*err[<unsigned int> i].imag))
    return err, wx

def MDDMA(np.ndarray[ndim=2, dtype=np.complex128_t] E,
                     int TrSyms, int Ntaps, unsigned int os,
                     double mu,
                     np.ndarray[ndim=2, dtype=np.complex128_t] wx,
                     np.ndarray[ndim=1, dtype=np.complex128_t] symbols):
    cdef np.ndarray[ndim=1, dtype=np.complex128_t] err = np.zeros(TrSyms, dtype=np.complex128)
    cdef np.ndarray[ndim=2, dtype=np.complex128_t] X = np.zeros([2,Ntaps], dtype=np.complex128)
    cdef unsigned int i, j, k
    cdef np.complex128_t Xest, R
    cdef unsigned int M = len(symbols)
    cdef unsigned int pols = E.shape[0]
    cdef unsigned int L = E.shape[1]
    for i in range(TrSyms):
        Xest = apply_filter(&E[0, i*os], Ntaps, <double complex *> wx.data, pols, L)
        R = det_symbol(<double complex *>symbols.data, M, Xest)
        err[<unsigned int> i] = (Xest.real**2 - R.real**2)*Xest.real + 1.j*(Xest.imag**2 - R.imag**2)*Xest.imag
        update_filter(&E[0,i*os], Ntaps, mu, err[<unsigned int> i], &wx[0,0], pols, L)
    return err, wx


