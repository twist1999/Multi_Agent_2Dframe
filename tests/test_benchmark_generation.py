from __future__ import annotations

import re
import unittest

from multiagent.benchmark import generate_benchmark_cases


class BenchmarkGenerationTests(unittest.TestCase):
    def test_shared_story_levels_have_matching_heights_across_bays(self) -> None:
        cases = generate_benchmark_cases(count=30, seed=20260506)
        pattern = re.compile(
            r"The (\w+) bay has (\d+) stories\. "
            r"The height of the .*? story are (.*?)(?=\. The length|\. Boundary Conditions)",
        )

        for case in cases:
            story_level_heights: dict[int, str] = {}
            matches = pattern.findall(case.prompt)
            self.assertGreater(len(matches), 0)
            for _, story_count_text, heights_text in matches:
                story_count = int(story_count_text)
                heights = re.findall(r"(\d+(?:\.\d+)?) m", heights_text)
                self.assertEqual(len(heights), story_count)
                for level, height in enumerate(heights, start=1):
                    if level in story_level_heights:
                        self.assertEqual(
                            story_level_heights[level],
                            height,
                            f"{case.case_id} has inconsistent height at story {level}",
                        )
                    else:
                        story_level_heights[level] = height


if __name__ == "__main__":
    unittest.main()
