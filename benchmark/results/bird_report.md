# BIRD-SQL Report: `expA_rest.json`

Local execution-accuracy (EX) run against 539 questions from `data/bird/splits/expA_rest.json` (public labels), using the same schema-grounded agent as the Chinook bake-off. **Not an official BIRD-SQL leaderboard submission** — the leaderboard scores a held-out test set through its own process; this is a comparable local proxy. Exec Acc is BIRD's official EX rule (`set(pred) == set(gold)`, `benchmark/evaluate.py:official_ex`); runs recorded before it existed fall back to the local contract-aware metric. Soft-F1 and R-VES (BIRD's other two metrics) are not implemented here.

| Model | Difficulty | N | Exec Acc | P50 (s) | P90 (s) | Repair % | $/query |
|---|---|---:|---:|---:|---:|---:|---:|
| `accounts/fireworks/models/deepseek-v4p1-flash` | unknown | 539 | 64.4% | 1.89 | 4.39 | 1.9% | $0.000609 |
| `accounts/fireworks/models/deepseek-v4p1-flash` | overall | 539 | 64.4% | 1.89 | 4.39 | 1.9% | $0.000609 |

## Per-database accuracy

| db_id | N | Exec Acc |
|---|---:|---:|
| `citeseer` | 2 | 0.0% |
| `genes` | 2 | 0.0% |
| `retail_world` | 3 | 0.0% |
| `college_completion` | 4 | 25.0% |
| `trains` | 6 | 33.3% |
| `professional_basketball` | 65 | 40.0% |
| `beer_factory` | 7 | 42.9% |
| `food_inspection` | 7 | 42.9% |
| `hockey` | 7 | 42.9% |
| `menu` | 7 | 42.9% |
| `simpson_episodes` | 7 | 42.9% |
| `superstore` | 7 | 42.9% |
| `movielens` | 55 | 43.6% |
| `craftbeer` | 2 | 50.0% |
| `human_resources` | 6 | 50.0% |
| `car_retails` | 7 | 57.1% |
| `cs_semester` | 7 | 57.1% |
| `law_episode` | 7 | 57.1% |
| `software_company` | 7 | 57.1% |
| `mondial_geo` | 6 | 66.7% |
| `shooting` | 3 | 66.7% |
| `works_cycles` | 6 | 66.7% |
| `address` | 7 | 71.4% |
| `airline` | 7 | 71.4% |
| `cars` | 7 | 71.4% |
| `computer_student` | 7 | 71.4% |
| `image_and_language` | 7 | 71.4% |
| `mental_health_survey` | 7 | 71.4% |
| `movie_3` | 7 | 71.4% |
| `public_review_platform` | 7 | 71.4% |
| `social_media` | 7 | 71.4% |
| `student_loan` | 7 | 71.4% |
| `world` | 7 | 71.4% |
| `regional_sales` | 109 | 72.5% |
| `sales` | 6 | 83.3% |
| `book_publishing_company` | 7 | 85.7% |
| `books` | 7 | 85.7% |
| `chicago_crime` | 7 | 85.7% |
| `shakespeare` | 7 | 85.7% |
| `ice_hockey_draft` | 46 | 87.0% |
| `app_store` | 6 | 100.0% |
| `cookbook` | 7 | 100.0% |
| `disney` | 7 | 100.0% |
| `legislator` | 7 | 100.0% |
| `movies_4` | 7 | 100.0% |
| `music_tracker` | 2 | 100.0% |
| `video_games` | 7 | 100.0% |
| **macro (mean over databases)** | 47 DBs | 63.8% |

## Failure analysis
- `address` #5117 (unknown): Result sets differ (category: wrong-result)
- `address` #5196 (unknown): Result sets differ (category: wrong-result)
- `airline` #5852 (unknown): Result sets differ (category: wrong-result)
- `airline` #5879 (unknown): Result sets differ (category: wrong-result)
- `beer_factory` #5268 (unknown): Result sets differ (category: wrong-result)
- `beer_factory` #5301 (unknown): Result sets differ (category: wrong-result)
- `beer_factory` #5344 (unknown): Result sets differ (category: wrong-result)
- `beer_factory` #5361 (unknown): Result sets differ (category: wrong-result)
- `book_publishing_company` #231 (unknown): Result sets differ (category: wrong-result)
- `books` #6049 (unknown): Result sets differ (category: wrong-result)
- `car_retails` #1556 (unknown): Result sets differ (category: wrong-result)
- `car_retails` #1595 (unknown): Result sets differ (category: wrong-result)
- `car_retails` #1638 (unknown): Result sets differ (category: wrong-result)
- `cars` #3095 (unknown): Result sets differ (category: wrong-result)
- `cars` #3099 (unknown): Result sets differ (category: wrong-result)
- `chicago_crime` #8753 (unknown): Result sets differ (category: wrong-result)
- `citeseer` #4142 (unknown): Result sets differ (category: wrong-result)
- `citeseer` #4150 (unknown): Result sets differ (category: wrong-result)
- `college_completion` #3691 (unknown): Result sets differ (category: wrong-result)
- `college_completion` #3721 (unknown): Result sets differ (category: wrong-result)
- `college_completion` #3750 (unknown): Result sets differ (category: wrong-result)
- `computer_student` #1001 (unknown): Result sets differ (category: wrong-result)
- `computer_student` #1018 (unknown): Result sets differ (category: wrong-result)
- `craftbeer` #8861 (unknown): Result sets differ (category: wrong-result)
- `cs_semester` #902 (unknown): Result sets differ (category: wrong-result)
- `cs_semester` #905 (unknown): Result sets differ (category: wrong-result)
- `cs_semester` #960 (unknown): Result sets differ (category: wrong-result)
- `food_inspection` #8780 (unknown): Result sets differ (category: wrong-result)
- `food_inspection` #8792 (unknown): Result sets differ (category: wrong-result)
- `food_inspection` #8819 (unknown): Result sets differ (category: wrong-result)
- `food_inspection` #8855 (unknown): Result sets differ (category: wrong-result)
- `genes` #2494 (unknown): Result sets match (category: wrong-result)
- `genes` #2504 (unknown): Result sets differ (category: wrong-result)
- `hockey` #7664 (unknown): Result sets differ (category: wrong-result)
- `hockey` #7702 (unknown): Result sets differ (category: wrong-result)
- `hockey` #7760 (unknown): Result sets differ (category: wrong-result)
- `hockey` #7761 (unknown): Result sets differ (category: wrong-result)
- `human_resources` #8956 (unknown): Result sets differ (category: wrong-result)
- `human_resources` #8965 (unknown): Result sets differ (category: wrong-result)
- `human_resources` #8987 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6969 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6986 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6988 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6990 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6991 (unknown): Result sets differ (category: wrong-result)
- `ice_hockey_draft` #6996 (unknown): Result sets differ (category: wrong-result)
- `image_and_language` #7574 (unknown): Result sets match (category: wrong-result)
- `image_and_language` #7608 (unknown): Result sets differ (category: wrong-result)
- `law_episode` #1257 (unknown): Result sets differ (category: wrong-result)
- `law_episode` #1324 (unknown): Result sets differ (category: wrong-result)
- `law_episode` #1337 (unknown): Result sets differ (category: wrong-result)
- `mental_health_survey` #4579 (unknown): Result sets differ (category: wrong-result)
- `mental_health_survey` #4612 (unknown): Result sets differ (category: wrong-result)
- `menu` #5483 (unknown): Result sets differ (category: wrong-result)
- `menu` #5498 (unknown): Result sets differ (category: wrong-result)
- `menu` #5562 (unknown): Result sets differ (category: wrong-result)
- `menu` #5572 (unknown): Result sets differ (category: wrong-result)
- `mondial_geo` #8278 (unknown): Result sets differ (category: wrong-result)
- `mondial_geo` #8415 (unknown): Result sets differ (category: wrong-result)
- `movie_3` #9214 (unknown): Result sets differ (category: wrong-result)
- `movie_3` #9374 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2255 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2256 (unknown): Result sets differ (category: repair-exhausted)
- `movielens` #2258 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2264 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2269 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2271 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2274 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2275 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2278 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2280 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2286 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2289 (unknown): Result sets match (category: repair-exhausted)
- `movielens` #2290 (unknown): Result sets match (category: repair-exhausted)
- `movielens` #2293 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2295 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2307 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2311 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2313 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2316 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2317 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2322 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2323 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2324 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2326 (unknown): Result sets match (category: repair-exhausted)
- `movielens` #2329 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2330 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2335 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2337 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2342 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `movielens` #2343 (unknown): Result sets differ (category: wrong-result)
- `movielens` #2344 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2799 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2805 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2813 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2815 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2818 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2820 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2827 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2830 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2834 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2839 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2842 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2849 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2855 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2857 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2858 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2870 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2876 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2879 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2886 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2899 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2907 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2910 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2912 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2917 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2918 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2919 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2920 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2926 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2929 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2931 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2934 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2936 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2942 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2943 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2944 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2945 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2946 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2951 (unknown): Result sets differ (category: wrong-result)
- `professional_basketball` #2952 (unknown): Result sets differ (category: wrong-result)
- `public_review_platform` #3890 (unknown): Result sets differ (category: wrong-result)
- `public_review_platform` #4017 (unknown): Execution failed: interrupted (category: repair-exhausted)
- `regional_sales` #2584 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2589 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2592 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2595 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2596 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2598 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2605 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2627 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2632 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2634 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2639 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2646 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2648 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2656 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2658 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2664 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2667 (unknown): Result sets match (category: wrong-result)
- `regional_sales` #2672 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2673 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2679 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2691 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2694 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2702 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2705 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2708 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2709 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2712 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2721 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2730 (unknown): Result sets differ (category: wrong-result)
- `regional_sales` #2731 (unknown): Result sets differ (category: wrong-result)
- `retail_world` #6317 (unknown): Gold execution failed: no such table: Order Details (category: wrong-result)
- `retail_world` #6524 (unknown): Gold execution failed: no such column: T2.CompanyName (category: wrong-result)
- `retail_world` #6612 (unknown): Gold execution failed: no such column: T2.CompanyName (category: wrong-result)
- `sales` #5415 (unknown): Result sets differ (category: wrong-result)
- `shakespeare` #2981 (unknown): Result sets differ (category: wrong-result)
- `shooting` #2462 (unknown): Gold execution failed: no such column: officer_count (category: wrong-result)
- `simpson_episodes` #4232 (unknown): Result sets differ (category: wrong-result)
- `simpson_episodes` #4240 (unknown): Result sets differ (category: wrong-result)
- `simpson_episodes` #4242 (unknown): Result sets differ (category: wrong-result)
- `simpson_episodes` #4298 (unknown): Result sets differ (category: wrong-result)
- `social_media` #797 (unknown): Result sets differ (category: wrong-result)
- `social_media` #804 (unknown): Result sets differ (category: wrong-result)
- `software_company` #8528 (unknown): Result sets differ (category: wrong-result)
- `software_company` #8582 (unknown): Result sets differ (category: wrong-result)
- `software_company` #8584 (unknown): Result sets differ (category: wrong-result)
- `student_loan` #4399 (unknown): Result sets differ (category: wrong-result)
- `student_loan` #4412 (unknown): Result sets differ (category: wrong-result)
- `superstore` #2386 (unknown): Result sets differ (category: wrong-result)
- `superstore` #2429 (unknown): Result sets differ (category: wrong-result)
- `superstore` #2437 (unknown): Result sets differ (category: wrong-result)
- `superstore` #2457 (unknown): Result sets differ (category: wrong-result)
- `trains` #714 (unknown): Result sets differ (category: wrong-result)
- `trains` #723 (unknown): Result sets differ (category: wrong-result)
- `trains` #728 (unknown): Result sets differ (category: wrong-result)
- `trains` #729 (unknown): Result sets differ (category: wrong-result)
- `works_cycles` #7269 (unknown): Result sets differ (category: wrong-result)
- `works_cycles` #7302 (unknown): Result sets differ (category: wrong-result)
- `world` #7840 (unknown): Result sets differ (category: wrong-result)
- `world` #7852 (unknown): Result sets differ (category: wrong-result)
