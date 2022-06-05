from collections import Counter
from operator import itemgetter
from random import randint, shuffle
from typing import List, Tuple

import pytest

from oml.samplers.balanced import BalanceBatchSampler

TLabelsPK = List[Tuple[List[int], int, int]]


def generate_valid_labels(num: int) -> TLabelsPK:
    """
    This function generates some valid inputs for samplers.
    It generates k instances for p labels.

    Args:
        num: Number of generated samples

    Returns:
        Samples in the following order: (labels, p, k)

    """
    labels_pk = []

    for _ in range(num):
        p, k = randint(2, 12), randint(2, 12)
        labels_list = [[label] * randint(2, 12) for label in range(p)]
        labels = [el for sublist in labels_list for el in sublist]

        shuffle(labels)
        labels_pk.append((labels, p, k))

    return labels_pk


@pytest.fixture()
def input_for_balance_batch_sampler() -> TLabelsPK:
    """
    Returns:
        Test data for sampler in the following order: (labels, p, k)

    """
    input_cases = [
        # ideal case
        ([0, 1, 2, 3, 0, 1, 2, 3], 2, 2),
        # repetation sampling is needed for label #3
        ([0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2], 2, 3),
        # check last batch behaviour:
        # last batch includes less than p labels (2 < 3)
        ([0, 1, 2, 3, 4, 0, 1, 2, 3, 4], 3, 2),
        # we need to drop 1 label during the epoch because
        # number of labels in data % p = 1
        ([0, 1, 2, 3, 0, 1, 2, 3], 3, 2),
        # several random cases
        ([0, 1, 2, 2, 1, 0, 1, 0, 2, 0, 1, 2], 3, 5),
        ([0, 1, 2, 2, 1, 0, 1, 0, 2, 0, 1, 2], 2, 3),
        ([0, 1, 2, 2, 1, 0, 1, 0, 2, 0, 1, 2], 3, 2),
    ]

    # (alekseysh) It was checked once with N = 100_000 before doing the PR
    num_random_cases = 100
    input_cases.extend((generate_valid_labels(num_random_cases)))

    return input_cases


def check_balance_batch_sampler_epoch(labels: List[int], p: int, k: int) -> None:
    """
    Args:
        labels: List of labels labels
        p: Number of labels in a batch
        k: Number of instances for each label in a batch

    """

    sampler = BalanceBatchSampler(labels, p, k)
    sampled_ids = list(sampler)

    sampled_labels = []
    # emulating of 1 epoch
    for i, batch_ids in enumerate(sampled_ids):
        batch_labels = itemgetter(*batch_ids)(labels)  # type: ignore

        labels_counter = Counter(batch_labels)
        num_batch_labels = len(labels_counter)
        num_batch_samples = list(labels_counter.values())
        cur_batch_size = len(batch_labels)
        sampled_labels.extend(list(labels_counter.keys()))

        # batch-level invariants
        assert len(set(batch_ids)) >= 4, set(batch_ids)  # type: ignore

        is_last_batch = i == sampler.batches_in_epoch - 1
        if is_last_batch:
            assert 1 < num_batch_labels <= p
            assert all(1 < el <= k for el in num_batch_samples)
            assert 2 * 2 <= cur_batch_size <= p * k
        else:
            assert num_batch_labels == p, (num_batch_labels, p)
            assert all(el == k for el in num_batch_samples)
            assert cur_batch_size == p * k

    # epoch-level invariants
    num_labels_in_data = len(set(labels))
    num_labels_in_sampler = len(set(sampled_labels))
    assert (num_labels_in_data == num_labels_in_sampler) or (num_labels_in_data == num_labels_in_sampler + 1)

    n_instances_sampled = sum(map(len, sampled_ids))  # type: ignore
    assert (num_labels_in_data - 1) * k <= n_instances_sampled <= num_labels_in_data * k, (
        n_instances_sampled,
        num_labels_in_data * k,
    )


def test_balance_batch_sampler(input_for_balance_batch_sampler) -> None:  # type: ignore
    """
    Args:
        input_for_balance_batch_sampler: List of (labels, p, k)

    """
    for labels, p, k in input_for_balance_batch_sampler:
        check_balance_batch_sampler_epoch(labels=labels, p=p, k=k)