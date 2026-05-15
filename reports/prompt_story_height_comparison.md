# Prompt Story Height Comparison

Seed: `20260506`; case count: `30`. Heights are listed from bottom story to top story. `L` is bay length in meters.

## Table 1: Previous Prompt Generator

In the previous version, each bay sampled story heights independently, so the same story level could have different heights in different bays.

| Case | Bay story counts and story heights from bottom to top |
|---:|---|
| 01 | B1: 3 stories; h=[3.6, 3.6, 4]; L=4.5<br>B2: 5 stories; h=[5, 5, 4, 3.6, 4.5]; L=8<br>B3: 5 stories; h=[7, 5.5, 3.6, 6, 5.5]; L=7.5 |
| 02 | B1: 2 stories; h=[5, 4]; L=4.5<br>B2: 4 stories; h=[4.5, 6, 3.6, 5]; L=8<br>B3: 4 stories; h=[4.5, 5, 5, 4]; L=6<br>B4: 4 stories; h=[7, 4, 3.6, 4]; L=7.5 |
| 03 | B1: 4 stories; h=[5, 5, 5, 6]; L=8<br>B2: 2 stories; h=[5, 4.5]; L=6<br>B3: 2 stories; h=[5, 5]; L=8 |
| 04 | B1: 3 stories; h=[7, 4, 3.6]; L=7.5<br>B2: 3 stories; h=[4, 4, 7]; L=7.5 |
| 05 | B1: 4 stories; h=[4, 4.5, 3.6, 4.5]; L=6<br>B2: 5 stories; h=[7, 3.6, 4, 4.5, 3.6]; L=6<br>B3: 2 stories; h=[5, 4.5]; L=5 |
| 06 | B1: 4 stories; h=[7, 3.6, 3.6, 3.6]; L=4.5<br>B2: 4 stories; h=[5.5, 5, 5, 7]; L=4.5 |
| 07 | B1: 2 stories; h=[5.5, 5.5]; L=7.5<br>B2: 3 stories; h=[5, 4, 5]; L=7.5<br>B3: 2 stories; h=[7, 6]; L=7.5<br>B4: 4 stories; h=[6, 7, 6, 4.5]; L=4.5<br>B5: 5 stories; h=[7, 4.5, 5.5, 4, 4.5]; L=4.5 |
| 08 | B1: 3 stories; h=[5, 5, 6]; L=7.5<br>B2: 5 stories; h=[6, 4, 4, 5, 3.6]; L=8<br>B3: 2 stories; h=[4.5, 7]; L=7.5<br>B4: 4 stories; h=[5.5, 4, 6, 5]; L=5 |
| 09 | B1: 2 stories; h=[7, 5.5]; L=4.5<br>B2: 3 stories; h=[4, 5, 3.6]; L=4.5<br>B3: 5 stories; h=[4.5, 5.5, 4, 4.5, 5]; L=5 |
| 10 | B1: 5 stories; h=[6, 4, 5.5, 7, 6]; L=5<br>B2: 4 stories; h=[6, 4.5, 7, 3.6]; L=8<br>B3: 4 stories; h=[4.5, 7, 4, 4]; L=4.5 |
| 11 | B1: 5 stories; h=[3.6, 5, 3.6, 5, 7]; L=4.5<br>B2: 4 stories; h=[6, 3.6, 5.5, 4.5]; L=4.5 |
| 12 | B1: 5 stories; h=[4, 4, 7, 6, 3.6]; L=5<br>B2: 5 stories; h=[4.5, 5.5, 5.5, 4.5, 7]; L=7.5<br>B3: 4 stories; h=[6, 3.6, 5, 5]; L=8<br>B4: 5 stories; h=[4, 4, 6, 5, 5.5]; L=6 |
| 13 | B1: 2 stories; h=[7, 4.5]; L=5<br>B2: 3 stories; h=[3.6, 5.5, 5]; L=5<br>B3: 2 stories; h=[7, 4.5]; L=5<br>B4: 4 stories; h=[5.5, 4.5, 4.5, 3.6]; L=7.5<br>B5: 3 stories; h=[6, 6, 5.5]; L=5 |
| 14 | B1: 2 stories; h=[7, 6]; L=4.5<br>B2: 3 stories; h=[5.5, 4.5, 4]; L=4.5 |
| 15 | B1: 4 stories; h=[4.5, 6, 5.5, 4.5]; L=6<br>B2: 4 stories; h=[5.5, 7, 4, 5.5]; L=5<br>B3: 5 stories; h=[5, 3.6, 4.5, 6, 6]; L=6<br>B4: 2 stories; h=[4, 4]; L=6<br>B5: 2 stories; h=[4, 3.6]; L=5 |
| 16 | B1: 4 stories; h=[3.6, 4.5, 4, 5.5]; L=4.5<br>B2: 5 stories; h=[4, 3.6, 5, 5, 5]; L=7.5<br>B3: 3 stories; h=[3.6, 4, 5]; L=6 |
| 17 | B1: 3 stories; h=[4.5, 7, 3.6]; L=6<br>B2: 3 stories; h=[4.5, 5.5, 3.6]; L=7.5<br>B3: 5 stories; h=[4, 5, 3.6, 4, 6]; L=8<br>B4: 2 stories; h=[7, 6]; L=5<br>B5: 2 stories; h=[5, 6]; L=8 |
| 18 | B1: 2 stories; h=[7, 5.5]; L=8<br>B2: 5 stories; h=[5.5, 3.6, 5, 5, 5]; L=7.5<br>B3: 4 stories; h=[4.5, 7, 7, 5]; L=5 |
| 19 | B1: 4 stories; h=[4.5, 7, 3.6, 6]; L=6<br>B2: 3 stories; h=[5.5, 5.5, 4]; L=8<br>B3: 3 stories; h=[7, 6, 4.5]; L=4.5<br>B4: 5 stories; h=[5, 5, 4, 5, 4.5]; L=8 |
| 20 | B1: 5 stories; h=[5.5, 4, 7, 7, 4.5]; L=5<br>B2: 4 stories; h=[4.5, 6, 3.6, 5.5]; L=5 |
| 21 | B1: 2 stories; h=[7, 4]; L=7.5<br>B2: 5 stories; h=[3.6, 3.6, 5.5, 3.6, 7]; L=8<br>B3: 3 stories; h=[4.5, 7, 4]; L=7.5<br>B4: 4 stories; h=[4.5, 6, 5, 6]; L=7.5<br>B5: 5 stories; h=[4.5, 6, 7, 4.5, 4.5]; L=7.5 |
| 22 | B1: 2 stories; h=[5.5, 7]; L=5<br>B2: 2 stories; h=[3.6, 5.5]; L=8 |
| 23 | B1: 3 stories; h=[5, 4.5, 3.6]; L=6<br>B2: 3 stories; h=[6, 5.5, 4.5]; L=8<br>B3: 2 stories; h=[3.6, 4]; L=7.5<br>B4: 3 stories; h=[3.6, 7, 4]; L=7.5 |
| 24 | B1: 5 stories; h=[4.5, 4.5, 4.5, 5, 4.5]; L=7.5<br>B2: 4 stories; h=[5, 5, 4.5, 6]; L=8<br>B3: 4 stories; h=[6, 5.5, 7, 4.5]; L=4.5<br>B4: 3 stories; h=[6, 5.5, 5]; L=6 |
| 25 | B1: 2 stories; h=[7, 4.5]; L=4.5<br>B2: 2 stories; h=[4.5, 4.5]; L=5<br>B3: 2 stories; h=[4.5, 5]; L=6<br>B4: 5 stories; h=[5, 5.5, 6, 4.5, 6]; L=7.5 |
| 26 | B1: 4 stories; h=[4.5, 7, 7, 3.6]; L=6<br>B2: 4 stories; h=[7, 4.5, 6, 4]; L=8 |
| 27 | B1: 5 stories; h=[5, 4.5, 5, 3.6, 7]; L=8<br>B2: 3 stories; h=[4, 5, 3.6]; L=8<br>B3: 5 stories; h=[6, 5.5, 6, 5, 4]; L=6<br>B4: 4 stories; h=[4, 5.5, 5, 6]; L=4.5<br>B5: 5 stories; h=[7, 4, 4.5, 5.5, 5.5]; L=5 |
| 28 | B1: 3 stories; h=[4, 5.5, 4]; L=5<br>B2: 2 stories; h=[4, 5]; L=4.5<br>B3: 5 stories; h=[4, 4.5, 5, 5.5, 4.5]; L=4.5<br>B4: 5 stories; h=[5.5, 4, 4.5, 4.5, 5]; L=6 |
| 29 | B1: 4 stories; h=[3.6, 5, 6, 5]; L=7.5<br>B2: 5 stories; h=[3.6, 4.5, 5, 7, 5.5]; L=4.5<br>B3: 2 stories; h=[4, 5.5]; L=4.5 |
| 30 | B1: 2 stories; h=[5, 7]; L=8<br>B2: 3 stories; h=[5.5, 7, 3.6]; L=7.5<br>B3: 3 stories; h=[4, 5, 5.5]; L=7.5 |

## Table 2: Current Prompt Generator

In the current version, a shared story-level height table is sampled first. Every bay that contains the same story level uses the same height for that level.

| Case | Bay story counts and story heights from bottom to top |
|---:|---|
| 01 | B1: 3 stories; h=[3.6, 3.6, 4]; L=4.5<br>B2: 5 stories; h=[3.6, 3.6, 4, 5, 5]; L=8<br>B3: 5 stories; h=[3.6, 3.6, 4, 5, 5]; L=7.5 |
| 02 | B1: 4 stories; h=[6, 4.5, 6, 4.5]; L=8<br>B2: 3 stories; h=[6, 4.5, 6]; L=8 |
| 03 | B1: 4 stories; h=[4.5, 5, 4, 4.5]; L=8<br>B2: 4 stories; h=[4.5, 5, 4, 4.5]; L=8 |
| 04 | B1: 4 stories; h=[5.5, 4.5, 3.6, 3.6]; L=7.5<br>B2: 3 stories; h=[5.5, 4.5, 3.6]; L=5<br>B3: 3 stories; h=[5.5, 4.5, 3.6]; L=5<br>B4: 3 stories; h=[5.5, 4.5, 3.6]; L=4.5<br>B5: 4 stories; h=[5.5, 4.5, 3.6, 3.6]; L=5 |
| 05 | B1: 5 stories; h=[7, 5, 4, 4, 7]; L=6<br>B2: 5 stories; h=[7, 5, 4, 4, 7]; L=7.5<br>B3: 5 stories; h=[7, 5, 4, 4, 7]; L=7.5<br>B4: 2 stories; h=[7, 5]; L=8<br>B5: 5 stories; h=[7, 5, 4, 4, 7]; L=8 |
| 06 | B1: 3 stories; h=[7, 4, 6]; L=5<br>B2: 4 stories; h=[7, 4, 6, 4.5]; L=4.5<br>B3: 4 stories; h=[7, 4, 6, 4.5]; L=7.5 |
| 07 | B1: 4 stories; h=[4, 5.5, 4, 5.5]; L=4.5<br>B2: 2 stories; h=[4, 5.5]; L=6<br>B3: 5 stories; h=[4, 5.5, 4, 5.5, 7]; L=4.5<br>B4: 4 stories; h=[4, 5.5, 4, 5.5]; L=5 |
| 08 | B1: 2 stories; h=[3.6, 5.5]; L=6<br>B2: 2 stories; h=[3.6, 5.5]; L=6 |
| 09 | B1: 5 stories; h=[4, 3.6, 4.5, 5, 5.5]; L=5<br>B2: 2 stories; h=[4, 3.6]; L=7.5<br>B3: 2 stories; h=[4, 3.6]; L=7.5<br>B4: 2 stories; h=[4, 3.6]; L=7.5 |
| 10 | B1: 5 stories; h=[5, 5.5, 5, 4, 4]; L=6<br>B2: 4 stories; h=[5, 5.5, 5, 4]; L=8<br>B3: 3 stories; h=[5, 5.5, 5]; L=5<br>B4: 4 stories; h=[5, 5.5, 5, 4]; L=6 |
| 11 | B1: 4 stories; h=[4, 4, 3.6, 7]; L=7.5<br>B2: 3 stories; h=[4, 4, 3.6]; L=5<br>B3: 5 stories; h=[4, 4, 3.6, 7, 3.6]; L=5<br>B4: 2 stories; h=[4, 4]; L=7.5<br>B5: 5 stories; h=[4, 4, 3.6, 7, 3.6]; L=4.5 |
| 12 | B1: 3 stories; h=[4, 4, 7]; L=8<br>B2: 4 stories; h=[4, 4, 7, 7]; L=5<br>B3: 5 stories; h=[4, 4, 7, 7, 4]; L=7.5<br>B4: 3 stories; h=[4, 4, 7]; L=4.5<br>B5: 2 stories; h=[4, 4]; L=6 |
| 13 | B1: 4 stories; h=[3.6, 6, 5, 3.6]; L=5<br>B2: 3 stories; h=[3.6, 6, 5]; L=8<br>B3: 3 stories; h=[3.6, 6, 5]; L=6<br>B4: 5 stories; h=[3.6, 6, 5, 3.6, 3.6]; L=4.5 |
| 14 | B1: 5 stories; h=[5.5, 4.5, 5.5, 7, 3.6]; L=7.5<br>B2: 2 stories; h=[5.5, 4.5]; L=4.5 |
| 15 | B1: 5 stories; h=[6, 6, 5, 4, 4]; L=7.5<br>B2: 5 stories; h=[6, 6, 5, 4, 4]; L=8<br>B3: 4 stories; h=[6, 6, 5, 4]; L=6 |
| 16 | B1: 3 stories; h=[6, 5, 5.5]; L=7.5<br>B2: 3 stories; h=[6, 5, 5.5]; L=7.5 |
| 17 | B1: 2 stories; h=[7, 4.5]; L=5<br>B2: 3 stories; h=[7, 4.5, 3.6]; L=5<br>B3: 2 stories; h=[7, 4.5]; L=5<br>B4: 4 stories; h=[7, 4.5, 3.6, 5.5]; L=7.5<br>B5: 3 stories; h=[7, 4.5, 3.6]; L=5 |
| 18 | B1: 3 stories; h=[3.6, 4, 7]; L=4.5<br>B2: 2 stories; h=[3.6, 4]; L=8<br>B3: 2 stories; h=[3.6, 4]; L=7.5<br>B4: 2 stories; h=[3.6, 4]; L=7.5 |
| 19 | B1: 4 stories; h=[7, 4.5, 4.5, 4]; L=5<br>B2: 3 stories; h=[7, 4.5, 4.5]; L=7.5 |
| 20 | B1: 4 stories; h=[5.5, 5, 3.6, 4.5]; L=4.5<br>B2: 3 stories; h=[5.5, 5, 3.6]; L=6 |
| 21 | B1: 4 stories; h=[6, 5.5, 4, 3.6]; L=8<br>B2: 3 stories; h=[6, 5.5, 4]; L=4.5 |
| 22 | B1: 3 stories; h=[5, 3.6, 4]; L=8<br>B2: 3 stories; h=[5, 3.6, 4]; L=8<br>B3: 2 stories; h=[5, 3.6]; L=5<br>B4: 5 stories; h=[5, 3.6, 4, 5, 6]; L=4.5<br>B5: 5 stories; h=[5, 3.6, 4, 5, 6]; L=6 |
| 23 | B1: 3 stories; h=[4.5, 7, 3.6]; L=6<br>B2: 3 stories; h=[4.5, 7, 3.6]; L=7.5<br>B3: 5 stories; h=[4.5, 7, 3.6, 4.5, 5.5]; L=8<br>B4: 2 stories; h=[4.5, 7]; L=5<br>B5: 2 stories; h=[4.5, 7]; L=8 |
| 24 | B1: 4 stories; h=[3.6, 7, 4, 5.5]; L=5<br>B2: 4 stories; h=[3.6, 7, 4, 5.5]; L=7.5 |
| 25 | B1: 5 stories; h=[4.5, 3.6, 4.5, 4.5, 5.5]; L=6<br>B2: 5 stories; h=[4.5, 3.6, 4.5, 4.5, 5.5]; L=8<br>B3: 4 stories; h=[4.5, 3.6, 4.5, 4.5]; L=8<br>B4: 5 stories; h=[4.5, 3.6, 4.5, 4.5, 5.5]; L=4.5<br>B5: 3 stories; h=[4.5, 3.6, 4.5]; L=7.5 |
| 26 | B1: 3 stories; h=[5, 4, 5]; L=7.5<br>B2: 4 stories; h=[5, 4, 5, 4.5]; L=6<br>B3: 5 stories; h=[5, 4, 5, 4.5, 6]; L=4.5 |
| 27 | B1: 5 stories; h=[5.5, 4, 7, 7, 4.5]; L=5<br>B2: 4 stories; h=[5.5, 4, 7, 7]; L=5 |
| 28 | B1: 5 stories; h=[5, 7, 5, 7, 3.6]; L=7.5<br>B2: 5 stories; h=[5, 7, 5, 7, 3.6]; L=7.5 |
| 29 | B1: 4 stories; h=[6, 7, 4.5, 4.5]; L=5<br>B2: 3 stories; h=[6, 7, 4.5]; L=4.5<br>B3: 4 stories; h=[6, 7, 4.5, 4.5]; L=4.5<br>B4: 5 stories; h=[6, 7, 4.5, 4.5, 5.5]; L=8<br>B5: 4 stories; h=[6, 7, 4.5, 4.5]; L=4.5 |
| 30 | B1: 2 stories; h=[5.5, 7]; L=5<br>B2: 2 stories; h=[5.5, 7]; L=8 |
