---
description: Check named rooms one by one (doors, lights, people, left-behind items) and report (a procedure; read this before any call). Asks which rooms and what to check, confirms, then visits.
---

# Room check

Use this skill when the user wants to know the state of one or more places
without going there: whether doors or windows are closed, lights are off,
anyone is present, or a given item was left behind.

This skill is a procedure. Follow the sections below in order. Do not skip
the questions, and do not move the robot before the user has confirmed.

## Information needed

Ask everything that is missing in one reply, numbered, at most three
questions. Ask only what the user has not already said.

1. Which rooms. Offer the names returned by `robonix/system/scene/list_regions`;
   accept "all of them".
2. What to check in each room, for example doors, lights, people, or a named
   item. One list applies to every room unless the user says otherwise.
3. Whether to report a problem as soon as it is found, or only at the end.
   Default: at the end.

Keep the questions short enough to be read aloud. When the user answers only
some of them, ask again for the rest only.

## Confirm before starting

Always confirm, even when the user answered everything at once. Repeat the
plan in one sentence (the rooms in visiting order, what will be checked) and
wait for the user to agree. Visit the rooms in the order the user gave, else
nearest first.

## Steps

For each room, in order:

1. Call `robonix/skill/room_check/visit` with the room's stable region ID.
   It plans a path through navigation, drives there and returns one photo.
2. Judge every check item from that photo only. When the item is outside the
   view or too unclear, the result is "cannot tell", never a guess.

When `arrived` is false, record the room as "not reached" with the reason
from `detail` and continue with the next room.

## Progress

Visit one place per plan, so there is a turn between places to report in.
After each room, say one short line, for example "Kitchen done: light on."
When the user asked for problems at once, say a problem as soon as it is
found and continue.

## Stopping early

If the user says stop, or changes the plan, stop after the current room and
report what was checked so far, marking the remaining rooms "not checked".

## Report

Two parts, in the user's language.

Spoken: one or two sentences, problems first, for example "All three rooms
checked. The kitchen light is on; everything else is fine."

Written, below it:

| Room | Item | Result | Photo |
|------|------|--------|-------|
| Kitchen | Light | On | #1 |

Results are one of: OK, a short description of the problem, cannot tell,
not reached, not checked. Number the photos in visiting order.
