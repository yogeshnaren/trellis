# Development-set genuine-error audit

The current v4p1 `train_dev` two-repeat run has 150 stable-wrong, 344 stable-correct and 7 mixed rows across 501 questions. Stable wrong **does not imply a genuine model error**: the training gold is noisy. No evaluation gate was read.

The prior 46-case hand audit tagged {'LD': 26, 'HC': 8, 'GE': 8, 'PA': 3, 'PATHOLOGY': 1}. Of those, {'LD': 26, 'HC': 6, 'PA': 3, 'GE': 6} remain stable-wrong under v4p1. This was a sample of failures, not a representative sample of all questions; its defect fraction must not be applied to cleaned dev or test.

The eight previously labeled genuine errors identify concrete mechanisms: unconstrained or incorrectly scoped joins, a dropped street-number constraint, the wrong location table, case-sensitive value mismatch, and arithmetic on text-encoded money or duration. These deserve narrowly tested fixes after the training-label screen. The 24 new, hash-selected stable-wrong rows (up to six per database plus hash-filled remainder, excluding prior labels) are saved as a review packet; they are unlabeled until question, SQL, and database results are inspected.

## New 24-case manual triage

`model_error_review_labels.csv` records **18 clear gold-label defects**, **one genuine model mistake**, **three cases where both SQLs are suspect**, and **two uncertain conventions**. This deliberately selected stable-failure packet is not a rate among all questions or a forecast for cleaned dev/test. The genuine case is movie row 18: the model ranked `$`-formatted net-worth strings as text, while gold converted them to numbers. By contrast, restaurant row 108's gold uses `county = 'Monterey'` (zero stored matches); the candidate uses stored `monterey county` (nine matches). Soccer row 323's gold names the wrong match and omits the requested player. An official-EX miss cannot automatically be a training target.

The next model-side tests should start from independently confirmed genuine failures such as money parsing, missing predicates and scoped joins. Do not fit a general rule to defective gold cases or inspect sealed gates for repairs.
