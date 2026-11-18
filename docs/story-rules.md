# Story rules: every sentence is a template

Team Success has no model-written prose. Every sentence that states a fact (player leads, daily
stories, takeaways, titles, descriptions, alt text, share text) is a template filled from data and
chosen by the rules below. A template states only what its fields prove. No template says a player
made, lifted, carried or dragged a team: it says what the record was.

## Player page lead (`scripts/leads.py`)

The first rule that applies writes the first sentence; sentences 2 and 3 follow.

| Rule | When | Sentence 1 | Fields |
|---|---|---|---|
| R0 | fewer than 3 completed seasons or fewer than 82 games | "Played {n} seasons for {k} teams; his teams went {W}–{L} in his games." (only sentence) | seasons, teams, record |
| R1 | 2+ titles | "His teams won {n} titles: {seasons}." | title seasons (runs collapse: "1990-91 to 1992-93") |
| R2 | 1 title | "His teams won one title, with the {season} {team}." | title season, champion's name that season |
| R3 | no title, 1+ Finals | "His teams reached the NBA Finals {once / n times} ({seasons}) without winning the title." | Finals seasons |
| R4 | no Finals, 1+ playoff trip | "His best final NBA finish was #{rank} of {teams}, with the {season} {team}." | best RNK (ties: latest), league size |
| R5 | never a playoff trip | "His teams missed the playoffs in all {n} of his seasons; the best final finish was #{rank} of {teams}, with the {season} {team}." | as R4 |

Sentence 2 (R1 to R5): "In his {G} games for {k} teams over {n} seasons they went {W}–{L} ({pct}),
{W − L} games over/under .500, with an average final finish of {avg}."

Sentence 3 (optional): the biggest one-season rise in final finish for the same franchise in two
consecutive seasons he played for it (the team he played most games for both seasons), only when
the rise is 8 places or more: "The biggest one-season rise in his career: the {team} went from
#{a} in {season 1} to #{b} in {season 2}." It reports the team's ranks, not a cause.

Counts per rule are printed by `scripts/build_site.py` on every build.

## Season board lead

"The {champion} finished #1 ({W}–{L}), the {runner-up} #2 ({W}–{L})." From the standings' RNK.

## Meta descriptions

Player: "{name}'s teams went {W}–{L} ({pct}) in his games, {span}: {winning} winning seasons,
{trips} playoff trips, {titles} titles, average final finish {avg}. Every season ranked, playoffs,
with and without him."

## Formats

Win rates 65.9%; gaps +26.0 pp from unrounded rates; records 706–366 (en dash); W − L with a
true minus sign; empty samples N/A; dates "Nov. 16, 2026".
