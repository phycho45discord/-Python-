#!/usr/bin/env python3
# external_sort.py
# 外部排序：把一个超大的二进制 int32 文件按升序排好
# 用法：python3 external_sort.py 文件名 一次能装入的整数个数
#
# 思路：
#   1) 把大文件切成若干小块，每块大小不超过「一次能装入的整数个数」
#   2) 每块用 list.sort() 排好，写到临时文件
#   3) 把所有临时文件用 K 路归并（最小堆）合成一个排好的文件
#   4) 删掉临时文件
#   第 2) 步用多进程并行，每块由一个进程处理

import os
import sys
import struct
import shutil
import heapq
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor

INT_SIZE = 4   # 一个 int32 占 4 个字节


def sort_chunk(args):
    """处理一块：读进来，排序，写到临时文件。"""
    in_file, temp_dir, chunk_id, chunk_size, num_ints = args

    # 这块在原文件里的位置和大小
    offset = chunk_id * chunk_size
    count  = min(chunk_size, num_ints - offset)

    # 读这块数据
    with open(in_file, 'rb') as f:
        f.seek(offset * INT_SIZE)
        raw = f.read(count * INT_SIZE)

    # 解出来，排序
    data = list(struct.unpack(f'{count}i', raw))
    data.sort()

    # 写到临时文件
    tmp = os.path.join(temp_dir, f'chunk_{chunk_id}.tmp')
    with open(tmp, 'wb') as f:
        f.write(struct.pack(f'{count}i', *data))
    return tmp


def main():
    # ----- 解析命令行参数 -----
    if len(sys.argv) != 3:
        print(f"用法: {sys.argv[0]} <输入文件> <一次能装入的整数个数>")
        sys.exit(1)

    in_file    = sys.argv[1]
    chunk_size = int(sys.argv[2])

    if chunk_size <= 0:
        print("块大小必须是正数")
        sys.exit(1)

    # 文件里有多少个整数
    file_size = os.path.getsize(in_file)
    if file_size % INT_SIZE != 0:
        print(f"文件大小不是 {INT_SIZE} 的倍数")
        sys.exit(1)
    num_ints = file_size // INT_SIZE

    # 输出文件和临时目录（都放在原文件同一个目录下）
    out_file = in_file + '.sorted'
    temp_dir = in_file + '.sort_tmp'

    # 清掉旧临时目录
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    # 空文件：直接建一个空输出
    if num_ints == 0:
        open(out_file, 'wb').close()
        print(f"排好了 -> {out_file}")
        return

    # 算一下要分几块、用几个进程
    num_chunks  = (num_ints + chunk_size - 1) // chunk_size
    num_workers = min(mp.cpu_count(), num_chunks)
    print(f"一共 {num_ints} 个整数，分 {num_chunks} 块，用 {num_workers} 个进程")

    # ========== 第 1 步：每块读进来排序写到临时文件（并行） ==========
    args = [(in_file, temp_dir, i, chunk_size, num_ints)
            for i in range(num_chunks)]
    with ProcessPoolExecutor(max_workers=num_workers) as pool:
        temp_files = list(pool.map(sort_chunk, args))

    # ========== 第 2 步：用最小堆把临时文件 K 路归并成一个大文件 ==========
    BUF = 4096   # 每次读 / 写 4096 个整数 = 16 KB

    # 给每个临时文件做一个"懒读取"生成器
    def reader(path, total):
        with open(path, 'rb') as f:
            left = total
            while left > 0:
                want = min(BUF, left)
                raw = f.read(want * INT_SIZE)
                if not raw:
                    break
                n = len(raw) // INT_SIZE
                left -= n
                for v in struct.unpack(f'{n}i', raw):
                    yield v

    readers = []
    for i, tf in enumerate(temp_files):
        offset = i * chunk_size
        count  = min(chunk_size, num_ints - offset)
        readers.append(reader(tf, count))

    # 把每个 reader 的第一个值塞进小顶堆
    heap = []
    for i, r in enumerate(readers):
        try:
            v = next(r)
            heapq.heappush(heap, (v, i))   # (值, 来自哪个 reader)
        except StopIteration:
            pass

    # 反复从堆里取最小的写到输出，再从同一个 reader 补一个
    with open(out_file, 'wb') as out:
        buf = []
        while heap:
            v, i = heapq.heappop(heap)
            buf.append(v)
            if len(buf) >= BUF:
                out.write(struct.pack(f'{len(buf)}i', *buf))
                buf = []
            try:
                nv = next(readers[i])
                heapq.heappush(heap, (nv, i))
            except StopIteration:
                pass
        if buf:
            out.write(struct.pack(f'{len(buf)}i', *buf))

    # ========== 第 3 步：清理临时目录 ==========
    shutil.rmtree(temp_dir)
    print(f"排好了 -> {out_file}")


if __name__ == '__main__':
    main()
