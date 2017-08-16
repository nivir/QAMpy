#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 27 17:11:02 2017

@author: mazurm
"""

import numpy as np

from dsp import equalisation, phaserecovery
from dsp.filter import moving_average


def pilot_based_foe(rec_symbs,pilot_symbs):
    """
    Frequency offset estimation for pilot-based DSP. Uses a transmitted pilot
    sequence to find the frequency offset from the corresponding aligned symbols.
    
    Gives higher accuracy than blind power of 4 based FFT for noisy signals. 
    Calculates the phase variations between the batches and does a linear fit
    to find the corresponding frequency offset. 
    
    Parameters
    ----------

    rec_symbs : array_like
        Complex symbols after initial Rx DSP
    pilot_symbs : array_like
        Complex pilot symbols transmitted

    Returns
    -------
    foe : float
        Estimated FO in terms of complex phase. Average over all modes
    foePerMode : array_like
        a FO estimate for each mode
    condNum : array_like
        Condition number of linear fit. Gives accuracy of estimation
    
    """

    rec_symbs = np.atleast_2d(rec_symbs)
    pilot_symbs = np.atleast_2d(pilot_symbs)
    npols = rec_symbs.shape[0]
    condNum = np.zeros([npols])
    foePerMode = np.zeros([npols])
    # Search over all polarization
    for l in range(npols):    
        phaseEvolution = np.unwrap(np.angle(pilot_symbs[l,:].conj()*rec_symbs[l,:]))
        # fit a first order polynomial to the unwrapped phase evolution
        freqFit = np.polyfit(np.arange(0,len(phaseEvolution)),phaseEvolution,1)
        foePerMode[l] = freqFit[0]/(2*np.pi)
        condNum[l] = freqFit[1]
    # Average over all modes used
    foe = np.mean(foePerMode)
    return foe, foePerMode, condNum

def pilot_based_cpe(rec_symbs, pilot_symbs, pilot_ins_ratio, num_average = 1, use_pilot_ratio = 1, max_num_blocks = None, remove_phase_pilots = True):
    """
    Carrier phase recovery using periodically inserted symbols.
    
    Performs a linear interpolation with averaging over n symbols to estimate
    the phase drift from laser phase noise to compensate for this.
    
    Parameters
    ----------
    rec_symbs : array_like
        Received symbols in block (first of each block is the pilot)
    pilot_symbs : array_like
        Corresponding pilot symbols. Index N is the first symbol in transmitted block N.
    pilot_ins_ratio : int
        Length of each block. Ex. 16 -> 1 pilot symbol followed by 15 data symbols
    num_average : int, optional
        Number of pilot symbols to average over to avoid noise. (Default: do not average)
    use_pilot_ratio :  int, optional
        Use ever n pilots. Can be used to sweep required rate.
    max_num_blocks : int, optional
        Maximum number of blocks to process. (Default: None, use all blocks in sequence)
    remove_phase_pilots : bool, optional
        Remove phase pilots after CPE
        
    Returns
    -------

    data_symbs : array_like
        Complex data symbols after pilot-aided CPE. Pilot symbols removed
    phase_trace : array_like
        Resulting phase trace of the CPE
    """

    rec_symbs = np.atleast_2d(rec_symbs)
    pilot_symbs = np.atleast_2d(pilot_symbs)
    npols = rec_symbs.shape[0]

    # Extract the pilot symbols
    numBlocks = np.floor(np.shape(rec_symbs)[1]/pilot_ins_ratio)
    # If selected, only process a limited number of blocks. 
    if (max_num_blocks is not None) and numBlocks > max_num_blocks:
        numBlocks = max_num_blocks   

    # Make sure that a given number of pilots can be used
    if (numBlocks % use_pilot_ratio):
        numBlocks -= (numBlocks % use_pilot_ratio)            

    # Adapt for number of blocks
    rec_pilots = rec_symbs[:,::pilot_ins_ratio] 
    rec_pilots = rec_pilots[:,:int(numBlocks)]
    rec_symbs = rec_symbs[:,:int(pilot_ins_ratio*numBlocks)]
    
    # Check that the number of blocks are equal and is valid
    numRefPilots = np.shape(pilot_symbs)[1]   
    if numBlocks > numRefPilots:

        numBlocks = numRefPilots
        rec_symbs = rec_symbs[:,numBlocks*pilot_ins_ratio]
        rec_pilots = rec_pilots[:,:numBlocks]
    elif numRefPilots > numBlocks:
        pilot_symbs = pilot_symbs[:,:numBlocks]
    
    # Remove every X pilot symbol if selected
    rec_pilots = rec_pilots[:,::use_pilot_ratio]
    pilot_symbs = pilot_symbs[:,::use_pilot_ratio]    
        
    # Should be an odd number to keey symmetry in averaging
    if not(num_average % 2):
        num_average += 1
    
    # Allocate output memory and process modes
    data_symbs = np.zeros([npols,np.shape(rec_symbs)[1]], dtype = complex)
    phase_trace = np.zeros([npols,np.shape(rec_symbs)[1]])
    for l in range(npols):
    
        # Calculate phase respons
        res_phase = pilot_symbs[l,:].conjugate()*rec_pilots[l,:]
        pilot_phase = np.unwrap(np.angle(res_phase))

        # Fix! Need moving average in numpy
        pilot_phase_average = np.transpose(moving_average(pilot_phase, num_average))
        pilot_phase = np.hstack([pilot_phase[:int((num_average-1)/2)], pilot_phase_average,np.ones(pilot_phase[:int((num_average-1)/2)].shape)*pilot_phase_average[-1]])
           
        # Pilot positions in the received data set
        pilot_pos = np.arange(0,len(pilot_phase)*pilot_ins_ratio*use_pilot_ratio,pilot_ins_ratio*use_pilot_ratio)
#        pilot_pos_int = np.arange(0,(len(pilot_phase)+1)*pilot_ins_ratio*use_pilot_ratio,pilot_ins_ratio*use_pilot_ratio)
        
        # Lineary interpolate the phase evolution
        phase_trace[l,:] = np.interp(np.arange(0,len(pilot_phase)*pilot_ins_ratio*use_pilot_ratio),\
                               pilot_pos,pilot_phase)

#        phase_func = interp1d(pilot_pos_int,np.hstack([pilot_phase,pilot_phase[-1]]),kind='linear')
#        phase_trace[l,:] = phase_func(np.arange(0,len(pilot_phase)*pilot_ins_ratio*use_pilot_ratio))
        
        # Compensate phase
        data_symbs[l,:] = rec_symbs[l,:]*np.exp(-1j*phase_trace[l,:])
        
        
    if remove_phase_pilots:
        pilot_pos = np.arange(0,np.shape(data_symbs)[1],pilot_ins_ratio)
        data_symbs = np.delete(data_symbs,pilot_pos, axis = 1)
        
    return data_symbs, phase_trace


def frame_sync(rx_signal, ref_symbs, os, frame_length = 2**16, mu = (1e-3,1e-3), M_pilot = 4, ntaps = (25,45), Niter = (10,30), adap_step = (True,True), method=('cma','sbd'),search_overlap = 2):
    """
    Locate and extract the pilot starting frame.
    
    Uses a CMA-based search scheme to located the initiial pilot sequence in
    the long data frame. 
    
    Parameters
    ----------
    rx_signal : array_like
        Received Rx signal
    ref_symbs : array_like
        Pilot sequence
    os : int
        Oversampling ratio
    frame_length : int, optional
        Total frame length including pilots and payload
    mu : tuple, optional
        CMA step size. Tuple(Search, Convergence)
    M_pilot : int, optional
        Order for pilot symbols. Should normally be QPSK and M=4
    ntaps : tuple, optional
        Number of T/2-spaced taps for equalization. Tuple(search, convergence)
    Niter : tuple, optional
        Number of iterations for the equalizer. Tuple(search, convergence)
    adap_step : tuple, optional
        Use adaptive step size.  Tuple(search, convergence)
    method : tuple, optional
        Equalizer methods to be used. See dsp equalisation of possible methods. Tuple(Search, Convergence)
    search_overlap : int, optional
        Overlap of subsequences in the test

    Returns
    -------
    eq_pilots : array_like
        Found pilot sequence after equalization
    shift_factor : array_like
        New starting point for initial equalization
    out_taps : array_like
        Taps for equalization of the whole signal
    foe_coarse : tuple
        Result of blind FOE used to sync the pilot sequence.
    """
    # Inital settings
    rx_signal = np.atleast_2d(rx_signal)
    ref_symbs = np.atleast_2d(ref_symbs)
    npols = rx_signal.shape[0]
    
    # Find the length of the pilot frame
    pilot_seq_len = len(ref_symbs[0,:])
    
    symb_step_size = int(np.floor(pilot_seq_len * os / search_overlap))
    
    # Adapt signal length
    sig_len = (np.shape(rx_signal)[1])
    if (sig_len > (frame_length + (search_overlap*2 + 5)*pilot_seq_len)*os):
        num_steps = int(np.ceil(((frame_length + (search_overlap*2 + 5) *pilot_seq_len)*os)/symb_step_size))
    else:
        num_steps = int(np.ceil(np.shape(rx_signal)[1] / symb_step_size))
    
    if not((ntaps[1]-ntaps[0])%os  ==  0):
        raise ValueError("Taps for search and convergence impropper configured")

    # Now search for every mode independent
    eq_pilots = np.zeros([npols,pilot_seq_len],dtype = complex)
    shift_factor = np.zeros(npols,dtype = int)
    out_taps = []
    for l in range(npols):

        # Search based on equalizer error. Avoid certain part in the beginning and
        # end to ensure that sufficient symbols can be used for the search
        sub_var = np.ones(num_steps)*1e2
        for i in np.arange(2+(search_overlap),num_steps-3-(search_overlap)):
            err_out = equalisation.equalise_signal(rx_signal[:,(i)*symb_step_size:(i+1+(search_overlap-1))*symb_step_size], os, mu[0], M_pilot,Ntaps = ntaps[0], Niter = Niter[0], method = method[0],adaptive_stepsize = adap_step[0])[1] 
            sub_var[i] = np.var(err_out[l,int(-symb_step_size/os+ntaps[0]):])
                       
        # Lowest variance of the CMA error
        minPart = np.argmin(sub_var)
        
        # Corresponding sequence
        shortSeq = rx_signal[:,(minPart)*symb_step_size:(minPart+1+(search_overlap-1))*symb_step_size]
        
        # Extract a longer sequence to ensure that the complete pilot sequence is found
        longSeq = rx_signal[:,(minPart-2-search_overlap)*symb_step_size:(minPart+3+search_overlap)*symb_step_size]

        # Use the first estimate to get rid of any large FO and simplify alignment
        wx1, err = equalisation.equalise_signal(shortSeq, os, mu[0], M_pilot,Ntaps = ntaps[0], Niter = Niter[0], method = method[0],adaptive_stepsize = adap_step[0])    
        seq_foe = equalisation.apply_filter(longSeq,os,wx1)
        foe_coarse = phaserecovery.find_freq_offset(seq_foe)
         
        # Apply filter taps to the long sequence
        symbs_out= equalisation.apply_filter(longSeq,os,wx1)
        symbs_out[l,:] = phaserecovery.comp_freq_offset(symbs_out[l,:], foe_coarse[l,:])
        # Check for pi/2 ambiguties
        max_phase_rot = np.zeros([4])
        found_delay = np.zeros([4])
        for k in range(4):
            # Find correlation for all 4 possible pi/2 rotations
            xcov = np.correlate(np.angle(symbs_out[l,:]*1j**k),np.angle(ref_symbs[l,:]))
            max_phase_rot[k] = np.max(xcov)
            found_delay[k] = np.argmax(xcov)

        # Select the best one
        symb_delay = int(found_delay[np.argmax(max_phase_rot)])

        # New starting sample
        shift_factor[l] = int((minPart-4)*symb_step_size + os*symb_delay)

        # Tap update and extract the propper pilot sequuence
        tap_cor = int((ntaps[1]-ntaps[0])/2)
        pilot_seq = rx_signal[:,shift_factor[l]-tap_cor:shift_factor[l]-tap_cor+pilot_seq_len*os+ntaps[1]-1]
        wx1, err = equalisation.equalise_signal(pilot_seq, os, mu[1], M_pilot,Ntaps = ntaps[1], Niter = Niter[1], method = method[0],adaptive_stepsize = adap_step[1])
        wx, err = equalisation.equalise_signal(pilot_seq, os, mu[1], M_pilot,wxy=wx1,Ntaps = ntaps[1], Niter = Niter[1], method = method[1],adaptive_stepsize = adap_step[1])
        symbs_out= equalisation.apply_filter(pilot_seq,os,wx)

        out_taps.append(wx)
        eq_pilots[l,:] = symbs_out[l,:]
    return eq_pilots, shift_factor, out_taps, foe_coarse

def find_const_phase_offset(rec_pilots, ref_symbs):
    """
    Finds a constant phase offset between the decoded pilot
    symbols and the transmitted ones

    Paramters
    ---------

    rec_pilots : array_like
        Complex received pilots (after FOE and alignment)
    ref_symbs : array_like
        Corresponding transmitted pilot symbols (aligned!)

    Returns
    -------
    phase_corr_pilots : array_like
        Phase corrected pilot symbols
    phase_corr : array_like
        Corresponding phase offset per mode
    """
    
    rec_pilots = np.atleast_2d(rec_pilots)
    ref_symbs = np.atleast_2d(ref_symbs)
    npols = rec_pilots.shape[0]

    phase_corr = np.zeros([npols,1],dtype = float)
    
    for l in range(npols):    
        phase_corr[l] = np.mean(np.angle(ref_symbs[l,:].conj()*rec_pilots[l,:]))

    return  phase_corr
    

def correct_const_phase_offset(symbs, phase_offsets):
    """
    Corrects a constant phase offset between the decoded pilot 
    symbols and the transmitted ones
    
    Parameters
    ----------

    symbs : array_like
        Complex symbols to be compensated
    phase_offsets : array_like
        Phase offset for each mode
        
    Returns
    -------

    symbs : array_like
        Symbols after phase rotation
    """
    
    symbs = np.atleast_2d(symbs)
    phase_offsets = np.atleast_2d(phase_offsets)
    npols = symbs.shape[0]

    for l in range(npols):
        symbs[l,:] = symbs[l,:] * np.exp(-1j*phase_offsets[l,0])

    return symbs



