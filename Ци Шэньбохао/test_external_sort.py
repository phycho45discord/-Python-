#!/usr/bin/env python3
# test_external_sort.py
# 测试：随机生成一批 int32，写成二进制文件，
#       然后调用 external_sort.py 排序，检查结果是不是排好的。
# 用法：python3 test_external_sort.py

import os
import sys
import struct
import random
import subprocess

N     = 5_000_000   # 500 万个整数，约 20 MB
CHUNK = 100_000      # 一块 10 万个，约 400 KB
BUF   = 1 << 16      # 一次写 65536 个整数

IN_FILE  = "test_in.bin"
OUT_FILE = "test_in.bin.sorted"


def write_random(path, n):
    """写 n 个随机 int32 到文件。"""
    with open(path, 'wb') as f:
        left = n
        while left > 0:
            take = min(BUF, left)
            data = [random.randint(-2**31, 2**31 - 1) for _ in range(take)]
            f.write(struct.pack(f'{take}i', *data))
            left -= take


def check_sorted(path, expected_count):
    """读一遍文件，看是不是升序。"""
    with open(path, 'rb') as f:
        prev = None
        seen = 0
        while True:
            raw = f.read(BUF * 4)
            if not raw:
                break
            for v in struct.unpack(f'{len(raw) // 4}i', raw):
                if prev is not None and v < prev:
                    print(f"第 {seen} 个位置不是升序")
                    return False
                prev = v
                seen += 1
    if seen != expected_count:
        print(f"数量不对：期待 {expected_count}，实际 {seen}")
        return False
    return True


def main():
    # 1. 生成随机数据
    print(f"生成 {N} 个随机 int32 ...")
    write_random(IN_FILE, N)

    # 2. 跑排序
    print(f"执行: python3 external_sort.py {IN_FILE} {CHUNK}")
    ret = subprocess.run(
        ['python3', 'external_sort.py', IN_FILE, str(CHUNK)],
        check=False)
    if ret.returncode != 0:
        print("排序失败")
        return 1

    # 3. 检查结果
    print("检查排序结果 ...")
    if not check_sorted(OUT_FILE, N):
        return 1
    print(f"OK: {N} 个整数检查通过")

    # 4. 清理
    os.remove(IN_FILE)
    os.remove(OUT_FILE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
