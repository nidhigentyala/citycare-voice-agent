# CityCare Voice AI Agent - Day 4 Evaluation Report

## Summary

Day 4 focused on testing and evaluating the CityCare Clinic Voice AI Agent using automated tests and simulated caller scenarios.

The agent was tested for clinic FAQs, booking, billing, verification, tool usage, handoffs, confirmation requirements, security checks, and error handling.

## Test results

### Unit tests

- Total tests: 12
- Passed: 12
- Failed: 0
- Success rate: 100%

The tests covered:
- Greeting
- Clinic hours
- Clinic address
- Parking information
- Off-topic questions
- Medical advice handling
- Free-slot lookup
- Booking confirmation
- Booking agent handoff
- Billing agent handoff
- Incorrect DOB security check
- Backend error handling

### Scenario tests

Six caller scenarios were prepared:

1. Normal booking
2. Confused caller
3. Angry cancellation
4. Caller changes mind
5. Wrong DOB
6. Medical advice request

Text and audio simulation testing was performed during Day 4.

## Task success rate

The automated unit-test success rate was:

**12 / 12 = 100%**

The unit tests passed successfully.

## Latency

The latency report produced the following measurements:

| Metric | P50 | P95 |
|---|---:|---:|
| E2E latency | 2.516 s | 5.251 s |
| LLM TTFT | 0.755 s | 1.560 s |
| TTS TTFB | 0.586 s | 0.958 s |
| End-of-turn delay | N/A | N/A |

The target E2E P95 latency is 1.5 seconds.

The measured E2E P95 latency was 5.251 seconds, which is above the target.

## Slowest turn

The slowest observed turns included:

- 8.158 seconds E2E latency
- 7.440 seconds E2E latency

One observed turn had approximately 3.191 seconds of LLM TTFT, showing that LLM processing can significantly contribute to end-to-end latency.

Other slow turns showed additional delay beyond the measured LLM and TTS processing.

## Bug fixed

During Day 4 testing, issues related to agent tool gating, verification, booking confirmation, and simulation behavior were identified and corrected.

The agent was updated so that sensitive operations require the appropriate verification and confirmation before proceeding.

## Top 3 problems

1. E2E latency is higher than the 1.5 second target.
2. Some turns have high LLM response latency.
3. Some turns have additional pipeline or turn-handling delay.

## Next steps

1. Optimize LLM and end-to-end response latency.
2. Investigate slow turn handling and pipeline delays.
3. Continue improving automated scenario coverage.
4. Monitor latency and reliability through CI.
5. Proceed to the next development task after completing the Day 4 testing requirements.