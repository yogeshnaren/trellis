# Paired comparison: `bird_raw_20260924T005317Z.jsonl` → `bird_raw_20260924T170715Z.jsonl`

## Comparability

- `prompt` differs (`effective_prompt_sha256_16`)
- `config` differs (`config_sha256_16`)
- `code` differs (`git_commit`)
- `code` differs (`code_state_sha256_16`)
- declared variable(s): ['code', 'config', 'prompt']

## Acceptance evidence (official EX): full comparison, coverage verified

501 shared questions; repeats old/new = 2/2 (each question scored as its mean over repeats). CIs: 95% bootstrap resampling questions within each database (2000 draws).

| Metric | Δ pts | 95% CI |
|---|---:|---|
| Row-weighted | +6.99 | [+4.49, +9.78] |
| Database macro | +6.91 | [+3.03, +10.98] |

Adopt only if **both** point estimates meet the change's declared minimum and both intervals exclude 0; subgroup tables below are for investigating regressions.

| Database | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| `movie` | 46 | 69.6% | 69.6% | +0.0 | 4 | 4 | 1.000 |
| `restaurant` | 117 | 58.1% | 70.1% | +11.5 | 1 | 15 | 0.001 |
| `sales_in_weather` | 80 | 40.0% | 52.5% | +11.2 | 4 | 14 | 0.031 |
| `soccer_2016` | 258 | 65.1% | 69.8% | +4.8 | 4 | 16 | 0.012 |

| Gold-SQL complexity | N | Old | New | Δ pts | Regressions | Fixes | McNemar p |
|---|---:|---:|---:|---:|---:|---:|---:|
| low | 243 | 71.2% | 78.2% | +6.8 | 4 | 22 | 0.001 |
| medium | 207 | 51.2% | 59.9% | +8.5 | 8 | 25 | 0.005 |
| high | 51 | 43.1% | 43.1% | +2.0 | 1 | 2 | 1.000 |

## Flips to audit against gold

Questions that flipped in every repeat. Gold labels are noisy, so read these before trusting a borderline result:

- fix: `movie` question 731 (row 1)
- REGRESSION: `movie` question 732 (row 2)
- REGRESSION: `movie` question 734 (row 4)
- fix: `movie` question 737 (row 7)
- fix: `movie` question 740 (row 10)
- REGRESSION: `movie` question 756 (row 26)
- fix: `movie` question 769 (row 39)
- REGRESSION: `movie` question 771 (row 41)
- fix: `restaurant` question 1679 (row 55)
- fix: `restaurant` question 1687 (row 63)
- fix: `restaurant` question 1703 (row 79)
- fix: `restaurant` question 1723 (row 99)
- fix: `restaurant` question 1728 (row 104)
- fix: `restaurant` question 1733 (row 109)
- fix: `restaurant` question 1751 (row 127)
- fix: `restaurant` question 1760 (row 136)
- fix: `restaurant` question 1765 (row 141)
- fix: `restaurant` question 1773 (row 149)
- fix: `restaurant` question 1775 (row 151)
- fix: `restaurant` question 1778 (row 154)
- fix: `restaurant` question 1780 (row 156)
- REGRESSION: `restaurant` question 1784 (row 160)
- fix: `restaurant` question 1785 (row 161)
- fix: `soccer_2016` question 1797 (row 173)
- fix: `soccer_2016` question 1803 (row 179)
- fix: `soccer_2016` question 1827 (row 203)
- fix: `soccer_2016` question 1828 (row 204)
- fix: `soccer_2016` question 1830 (row 206)
- fix: `soccer_2016` question 1831 (row 207)
- fix: `soccer_2016` question 1832 (row 208)
- fix: `soccer_2016` question 1837 (row 213)
- fix: `soccer_2016` question 1877 (row 253)
- fix: `soccer_2016` question 1904 (row 280)
- fix: `soccer_2016` question 1916 (row 292)
- fix: `soccer_2016` question 1941 (row 317)
- fix: `soccer_2016` question 1945 (row 321)
- fix: `soccer_2016` question 1963 (row 339)
- REGRESSION: `soccer_2016` question 2019 (row 395)
- fix: `sales_in_weather` question 8142 (row 426)
- fix: `sales_in_weather` question 8161 (row 445)
- REGRESSION: `sales_in_weather` question 8175 (row 459)
- fix: `sales_in_weather` question 8176 (row 460)
- REGRESSION: `sales_in_weather` question 8179 (row 463)
- fix: `sales_in_weather` question 8180 (row 464)
- fix: `sales_in_weather` question 8181 (row 465)
- fix: `sales_in_weather` question 8186 (row 470)
- fix: `sales_in_weather` question 8187 (row 471)
- fix: `sales_in_weather` question 8189 (row 473)
- fix: `sales_in_weather` question 8208 (row 492)
- fix: `sales_in_weather` question 8209 (row 493)

