from oas.ext.algorithm.lcp import get_lcs_length


class PathLookbackLCSV3:
    """
    V3 — no optimizations. Stores all paths in a flat list and does a linear scan.
    """

    def __init__(self):
        self.index = 0
        self.paths: "list[str]" = []

    def get_lcs(self, path, min_length=1, max_length=None):
        """
        Args:
            path (str):
            min_length (int): Minimum LCS length for a candidate.
            max_length (int | None): Maximum LCS length for a candidate.

        Returns:
            tuple[int, int]: lookback, lcs_length
                lookback is 1-based distance to the matched item, 0 if no match
        """
        best_index = -1
        best_length = 0
        current_index = self.index

        for prev_index, prev in enumerate(self.paths):
            length = get_lcs_length(path, prev)
            if length < min_length:
                continue
            if max_length is not None and length > max_length:
                continue
            if length > best_length:
                best_index = prev_index
                best_length = length
            elif length == best_length and prev_index > best_index:
                best_index = prev_index

        if best_length:
            return current_index - best_index, best_length
        return 0, 0

    def add_path(self, path):
        """
        Args:
            path (str):
        """
        self.paths.append(path)
        self.index += 1
