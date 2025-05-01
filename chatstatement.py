#!/usr/bin/env python

#%%
from enum import Enum
import dataclasses
import glob
import Levenshtein

#%%
@dataclasses.dataclass
class Statement:
    name:str
    message:str
    translated_text:str

def is_name_line(line:str):
    d = Levenshtein.distance("SHIMIZU Wataru".lower(), line.lower())
    return d <= 3

def parse_lines(all_lines:list[str]) -> list[Statement]:
    if len(all_lines) == 1 and len(all_lines[0]) == 0:
        return []
    lines_list:list[list:str] = []
    lines:list[str] = []
    for i, line in enumerate(all_lines):
        #print(f"{i} {line}")
        if is_name_line(line):
            if len(lines) > 0:
                lines_list.append(lines)
            lines = [line]
        else:
            if not line == "":
                lines.append(line)
        if i == len(all_lines)-1:
            lines_list.append(lines)

    stats:list[Statement] = []
    for lines in lines_list:
        if not is_name_line(lines[0]):
            continue
        name = lines[0]
        message = " ".join(lines[1:])
        stat = Statement(name=name, message=message, translated_text="")
        stats.append(stat)
    return stats

#%%
class StatementBuffer:
    def __init__(self):
        self.stats:list[Statement] = []
        self.last_n_updated = -1

    # Retval: last n statements were updated
    def update(self, new_stats:list[Statement]) -> int:
        # print("  prev all")
        # for stat in self.stats:
        #     print(f"    {stat.message}")
        # print("  new all")
        # for stat in new_stats:
        #     print(f"    {stat.message}")
        if len(new_stats) == 0:
            return 0

        n_compare = min(len(self.stats), len(new_stats))
        for i_n_compare in reversed(range(1, n_compare+1)):
            tmp_prev_stats = self.stats[-i_n_compare:]
            tmp_new_stats = new_stats[0:i_n_compare]
            tmp_new_remaining_stats = new_stats[i_n_compare:]
            # print(f"{i_n_compare} prev")
            # for stat in tmp_prev_stats:
            #     print(f"  {stat.message}")
            # print(f"{i_n_compare} new")
            # for stat in tmp_new_stats:
            #     print(f"  {stat.message}")
            comp_ret = self.compare_partial_stats(tmp_prev_stats, tmp_new_stats)
            if comp_ret == 0:
                self.stats.extend(tmp_new_remaining_stats)
                return len(tmp_new_remaining_stats)
            if comp_ret == 1:
                self.stats[-1] = tmp_new_stats[-1]
                self.stats.extend(tmp_new_remaining_stats)
                return len(tmp_new_remaining_stats) + 1
        self.stats.extend(new_stats)
        self.last_n_updated = len(new_stats)
        return self.last_n_updated

    @classmethod
    def is_statement_similar(cls, prev_stat:Statement, new_stat:Statement):
        d = Levenshtein.distance(prev_stat.message.lower(), new_stat.message.lower())
        return d <= 3

    @classmethod
    def is_statement_updated(cls, prev_stat:Statement, new_stat:Statement):
        if len(new_stat.message) <= len(prev_stat.message):
            return False
        part_new_message = new_stat.message[0:len(prev_stat.message)]
        d = Levenshtein.distance(prev_stat.message.lower(), part_new_message.lower())
        return d <= 3

    # Return All_Similar, Last_Updated or Other
    @classmethod
    def compare_partial_stats(cls, prev_stats:list[Statement], new_stats:list[Statement]):
        #print("compare_partial_stats")
        assert(len(prev_stats) == len(new_stats))
        assert(not len(prev_stats) == 0)

        is_all_similar_except_last = True
        if len(prev_stats) >= 2:
            for prev_stat, new_stat in zip(prev_stats[:-1], new_stats[:-1]):
                is_all_similar_except_last = is_all_similar_except_last and cls.is_statement_similar(prev_stat, new_stat)

        last_prev_stat = prev_stats[-1]
        last_new_stat = new_stats[-1]
        is_last_similar = cls.is_statement_similar(last_prev_stat, last_new_stat)
        is_last_updated = cls.is_statement_updated(last_prev_stat, last_new_stat)

        if is_last_similar and is_all_similar_except_last:
            return 0 # All similar
        if is_last_updated and is_all_similar_except_last:
            return 1 # Last_Updated
        return 2     # Other

if __name__ == "__main__":
    ocr_paths = [path.replace("\\", "/") for path in sorted(list(glob.glob("./ocr/ocr-*.txt")))]
    stats_list:list[list[Statement]] = []
    for ocr_path in ocr_paths:
        #print(ocr_path)
        with open(ocr_path) as f:
            lines = [line.strip() for line in f.readlines()]
        stats = parse_lines(lines)
        stats_list.append(stats)

    sb= StatementBuffer()
    for i, stats in enumerate(stats_list):
        print(f"{i}")
        n = sb.update(stats)
        for j, stat in enumerate(sb.stats):
            was_updated = j >= len(sb.stats) - n
            print(f"  {int(was_updated)}  {stat.message}")
