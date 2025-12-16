# VibeSurf Gemini ASR Race Condition Fix

## Problem Description
The Gemini ASR (Automatic Speech Recognition) streaming implementation in VibeSurf has a race condition that causes:
- Premature timeouts during streaming
- Incomplete transcription results
- Unreliable voice input processing

## Root Cause
The issue occurs in the `voice_asr.py` module where the Gemini streaming ASR implementation doesn't properly handle asynchronous response chunks, leading to race conditions between:
1. Stream chunk arrival timing
2. Timeout mechanisms
3. Result aggregation logic

## Expected Behavior
- Gemini ASR should reliably wait for all streaming chunks
- Timeout should only trigger after genuine inactivity
- Transcription results should be complete and stable

## Implementation Tasks
1. Locate `voice_asr.py` in the `vibe_surf` directory
2. Identify the Gemini ASR streaming class/function
3. Add proper synchronization for streaming chunks
4. Implement exponential backoff or adaptive timeout
5. Ensure proper cleanup and error handling
6. Test with various input lengths and network conditions

## Testing
- Manual verification with voice input
- Edge cases: long pauses, quick speech, network delays
- Verify no regression in other ASR providers (if any)

