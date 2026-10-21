# Sources and data boundaries

Reproduction reference: [Recommenders](https://github.com/recommenders-team/recommenders),
commit aa8332189cd495be6ffaa7e1c8054f1c180b5ef3, MIT.
The original upstream checkout and its LICENSE are retained outside this repo.
The baseline report identifies exact notebooks and adaptations.

MovieLens data is provided by GroupLens for research. Read the original
[100K terms](https://files.grouplens.org/datasets/movielens/ml-100k-README.txt) and
[1M terms](https://files.grouplens.org/datasets/movielens/ml-1m-README.txt).
This repository does not redistribute raw ratings, user metadata, or model
artifacts containing historical user interactions. Download scripts retrieve
data directly from GroupLens. No commercial-use permission is asserted.

Cornac implements BPR; this work does not claim to invent BPR or SAR.
Own contributions are the temporal protocol, controlled reranking experiments,
validation and test separation, service, tests and learning materials.
AI-assisted implementation must still be studied, explained and verified by
the portfolio owner; generated work alone is not evidence of personal mastery.
