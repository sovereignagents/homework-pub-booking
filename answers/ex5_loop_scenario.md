# Ex5 — Edinburgh research loop scenario

## Your answer



sess_10b97779ceb2-early exit: The trace shows an agent-flow failure, Initially, the planner received the correct 
context, including party size 6, date 2026-05-02, time 19:19, and the Haymarket area, but it split the work into 
5 subgoals. This is far more than the expected  4 as many as the tools, whicb increases already the chance for failure.
The executor successfully found the correct venue, haymarket_tap, then prematurely called complete_task 
for that subgoal. It later fetched the weather for the correct date, but when it reached cost calculation 
it no longer carried forward the venue_id which had found from the task, so it handed off instead of calling 
calculate_cost. Verify dataflow did not detect this failure as no final flyer was created.This is now edited 
in the latest verify_dataflow.


Also during development I observed situation where  during the dataflow the venus search\
selected 'Haymarket_tap' but subsequnet tools like calculator  hallucinated and that was carried over to \
the flyer. In the original verify-dataflow this was a pass , falsely.
In the editted version I added condition that extracted infomration from all the used tools\
need to match for stricter pass.

## Citations

- sessions/sess_*/logs/trace.jsonl — tool call sequence
- sessions/sess_*/workspace/flyer.md — the produced flyer
