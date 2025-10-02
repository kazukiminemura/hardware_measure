# monitor_hw_usage.py
import time
import psutil
import itertools
import math
from collections import defaultdict

# AI活動検出のインポート
from ai_activity_detector import AIActivityDetector, NPUUsageEstimator, format_ai_activity_status

# ----- GPU/NPU (PDH) via pywin32 -----
try:
    import win32pdh
    HAS_PDH = True
except Exception:
    HAS_PDH = False



REFRESH_SEC = 1.0

class RunningAverage:
    def __init__(self):
        self._total = 0.0
        self._count = 0

    def add(self, value):
        if value is None:
            return
        self._total += float(value)
        self._count += 1

    def has_samples(self):
        return self._count > 0

    def average(self):
        return self._total / self._count if self._count else 0.0

class PDHWildcardReader:
    """
    Read Windows Performance Counters with wildcard instances,
    e.g. r'\\GPU Engine(*)\\Utilization Percentage'
         r'\\NPU Engine(*)\\Utilization Percentage' (存在すれば)
    """
    def __init__(self, path_pattern):
        self.path_pattern = path_pattern
        self.query = None
        self.counters = []  # list of (hCounter, path)

    def _build(self):
        # Expand wildcard to concrete counter paths
        paths = win32pdh.ExpandCounterPath(self.path_pattern)
        if not paths:
            return False
        self.query = win32pdh.OpenQuery()
        self.counters = []
        for p in paths:
            try:
                h = win32pdh.AddCounter(self.query, p)
                self.counters.append((h, p))
            except Exception:
                # 一部のカウンタは追加に失敗することがあるのでスキップ
                pass
        # 初回サンプル
        win32pdh.CollectQueryData(self.query)
        return len(self.counters) > 0

    def available(self):
        if not HAS_PDH:
            return False
        try:
            return self._build()
        except Exception:
            return False

    def sample(self):
        """
        Returns dict: {instance_label: value_percent}
        """
        if not self.query or not self.counters:
            return {}
        time.sleep(0.2)  # PDHは2回目以降の差分で%を計算するので短い待ち
        win32pdh.CollectQueryData(self.query)
        data = {}
        for h, p in self.counters:
            try:
                t, val = win32pdh.GetFormattedCounterValue(h, win32pdh.PDH_FMT_DOUBLE)
                # インスタンス名抽出（\Object(instance)\Counter 形式）
                inst = p
                # 見やすくするため「engtype_#」等を短縮
                if '(' in p and ')' in p:
                    inst = p[p.find('(')+1:p.find(')')]
                data[inst] = float(val)
            except Exception:
                pass
        return data

def summarize_engine_util(engine_dict, include_names=None, exclude_contains=None):
    """
    PDHのGPU/NPU Engine*(インスタンス)を集計。
    - include_names: サマリに含めたいキーワード（例: 'engtype_3D'）
    - exclude_contains: 除外キーワード
    return: (overall_percent, top5_list)
    """
    filt = {}
    for k, v in engine_dict.items():
        # include_names が指定されている場合、そのキーワードを含むもののみ
        if include_names and not any(tag.lower() in k.lower() for tag in include_names):
            continue
        # exclude_contains が指定されている場合、そのキーワードを含むものを除外
        if exclude_contains and any(tag.lower() in k.lower() for tag in exclude_contains):
            continue
        # 無効・NaNを除外
        if v is None or (isinstance(v, float) and (math.isnan(v) or v < 0)):
            continue
        filt[k] = v

    if not filt:
        return (0.0, [])
    
    # 3D/Compute Engine専用の場合、より精密な計算
    if include_names and any(name.lower() in ['3d', 'compute'] for name in include_names):
        # 3D/Compute Engineの場合、最大値を採用（並列処理を考慮）
        if filt:
            overall = max(filt.values())
        else:
            overall = 0.0
    else:
        # 従来通りの平均値計算
        top = sorted(filt.items(), key=lambda x: x[1], reverse=True)[:5]
        overall = sum(v for _, v in top) / len(top) if top else 0.0
    
    # トップ5のリストは常に作成
    top = sorted(filt.items(), key=lambda x: x[1], reverse=True)[:5]
    return (overall, top)

def format_top_list(top_list, max_items=5):
    return ", ".join([f"{k}:{v:.0f}%" for k, v in top_list[:max_items]])

def human_bytes(n):
    if n is None:
        return "n/a"
    units = ['B','KB','MB','GB','TB']
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0
        i += 1
    return f"{f:.1f}{units[i]}"

def human_bytes_per_s(n):
    if n is None:
        return "n/a"
    units = ['B/s','KB/s','MB/s','GB/s','TB/s']
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0
        i += 1
    return f"{f:.1f}{units[i]}"

def print_header():
    print("="*78)
    print(" Windows Hardware Utilization Monitor (Task Manager-like) ")
    print("="*78)
    print("Ctrl+C to stop\n")

def print_npu_status():
    """NPUデバイスの状況を表示"""
    print("NPU Detection Status:")
    print("-" * 40)
    
    # Intel AI Boost の検出
    intel_ai_boost_found = False
    try:
        import wmi
        c = wmi.WMI()
        devices = c.Win32_PnPEntity()
        for device in devices:
            device_name = str(getattr(device, 'Name', ''))
            if 'Intel(R) AI Boost' in device_name:
                intel_ai_boost_found = True
                print(f"✓ Intel AI Boost NPU detected: {device_name}")
                break
    except Exception:
        pass
    
    if not intel_ai_boost_found:
        print("✗ Intel AI Boost NPU not detected")
    
    # Performance Counter の確認
    try:
        import win32pdh
        try:
            paths = win32pdh.ExpandCounterPath(r"\NPU Engine(*)\Utilization Percentage")
            if paths:
                print(f"✓ NPU Performance Counters available: {len(paths)} instances")
            else:
                print("✗ NPU Performance Counters not available")
        except Exception:
            print("✗ NPU Performance Counters not available")
    except ImportError:
        print("✗ win32pdh not available for NPU counter check")
    
    if intel_ai_boost_found:
        print("\nNOTE: Intel AI Boost NPU is present but may require:")
        print("  - Windows 11 24H2 or later for full PDH counter support")
        print("  - Latest Intel Graphics drivers")
        print("  - NPU workload to show meaningful utilization")
        print("  - Use Task Manager > Performance tab to verify NPU visibility")
    else:
        print("\nNOTE: No NPU detected on this system")
    
    print()  # 空行


def main():
    print_header()
    print_npu_status()

    # CPU priming
    psutil.cpu_percent(interval=None)

    # PDH readers
    gpu_reader = None
    npu_reader = None
    if HAS_PDH:
        try:
            gpu_reader = PDHWildcardReader(r"\GPU Engine(*)\Utilization Percentage")
            if not gpu_reader.available():
                gpu_reader = None
        except Exception:
            gpu_reader = None

        try:
            # Windows 11/24H2 以降対応デバイスで存在する可能性あり
            npu_reader = PDHWildcardReader(r"\NPU Engine(*)\Utilization Percentage")
            if not npu_reader.available():
                npu_reader = None
        except Exception:
            npu_reader = None
        
        # Intel AI Boost デバイスの存在確認
        intel_ai_boost_detected = False
        try:
            import wmi
            c = wmi.WMI()
            devices = c.Win32_PnPEntity()
            for device in devices:
                device_name = str(getattr(device, 'Name', ''))
                if 'Intel(R) AI Boost' in device_name:
                    intel_ai_boost_detected = True
                    break
        except Exception:
            pass



    avg_cpu = RunningAverage()
    avg_mem = RunningAverage()
    avg_gpu = RunningAverage()
    avg_npu = RunningAverage()
    avg_disk_read = RunningAverage()
    avg_disk_write = RunningAverage()
    avg_net_send = RunningAverage()
    avg_net_recv = RunningAverage()

    # AI活動検出器とNPU推定器の初期化
    ai_detector = AIActivityDetector()
    npu_estimator = NPUUsageEstimator()
    ai_detector.start_monitoring()

    last_disk_io = psutil.disk_io_counters()
    last_net_io = psutil.net_io_counters()
    last_sample_ts = time.monotonic()

    while True:
        try:
            loop_start = time.monotonic()
            elapsed = max(loop_start - last_sample_ts, 1e-6)

            # ----- CPU -----
            cpu_overall = psutil.cpu_percent(interval=None)
            cpu_per = psutil.cpu_percent(interval=None, percpu=True)
            avg_cpu.add(cpu_overall)

            # ----- Memory -----
            vm = psutil.virtual_memory()
            mem_percent = vm.percent
            avg_mem.add(mem_percent)

            # ----- Disk (throughput per second) -----
            disk_io = psutil.disk_io_counters()
            disk_read_rate = None
            disk_write_rate = None
            if last_disk_io is not None:
                disk_read_delta = max(0.0, disk_io.read_bytes - last_disk_io.read_bytes)
                disk_write_delta = max(0.0, disk_io.write_bytes - last_disk_io.write_bytes)
                disk_read_rate = disk_read_delta / elapsed
                disk_write_rate = disk_write_delta / elapsed
                avg_disk_read.add(disk_read_rate)
                avg_disk_write.add(disk_write_rate)
            last_disk_io = disk_io

            # ----- Network (throughput per second) -----
            net = psutil.net_io_counters()
            net_send_rate = None
            net_recv_rate = None
            if last_net_io is not None:
                net_send_delta = max(0.0, net.bytes_sent - last_net_io.bytes_sent)
                net_recv_delta = max(0.0, net.bytes_recv - last_net_io.bytes_recv)
                net_send_rate = net_send_delta / elapsed
                net_recv_rate = net_recv_delta / elapsed
                avg_net_send.add(net_send_rate)
                avg_net_recv.add(net_recv_rate)
            last_net_io = net

            # ----- GPU via PDH (Compute Engine focused) -----
            gpu_now = None
            gpu_top = []
            if gpu_reader:
                gsample = gpu_reader.sample()
                g_overall, g_top = summarize_engine_util(
                    gsample,
                    include_names=["Compute", "engtype_Compute"],  # Compute Engine のみを対象
                    exclude_contains=["Copy", "Video", "3D"]  # Copy, Video, 3D系を除外
                )
                gpu_top = g_top
                if g_top:
                    gpu_now = g_overall

            # ----- NPU via PDH -----
            npu_now = None
            npu_top = []
            if npu_reader:
                nsample = npu_reader.sample()
                n_overall, n_top = summarize_engine_util(
                    nsample,
                    include_names=None,
                    exclude_contains=None
                )
                npu_top = n_top
                if n_top:
                    npu_now = n_overall



            if gpu_now is not None:
                avg_gpu.add(gpu_now)
            if npu_now is not None:
                avg_npu.add(npu_now)

            # ----- AI活動検出とNPU使用推定 -----
            current_ai_activity = ai_detector.get_current_ai_activity()
            
            # NPU推定値の更新
            if current_ai_activity['active']:
                npu_estimator.update_ai_cpu(cpu_overall)
            else:
                npu_estimator.update_baseline_cpu(cpu_overall)
            
            # AI活動状況の取得
            ai_status, npu_estimated = format_ai_activity_status(ai_detector, npu_estimator)

            print("\n" + "-"*78)

            cpu_avg_str = f"{avg_cpu.average():5.1f}%" if avg_cpu.has_samples() else "  n/a"
            cpu_line = "CPU   : avg {} | curr {:5.1f}% | per-core: {}".format(
                cpu_avg_str,
                cpu_overall,
                ", ".join(f"{p:4.0f}%" for p in cpu_per)
            )
            print(cpu_line)

            mem_avg_str = f"{avg_mem.average():5.1f}%" if avg_mem.has_samples() else "  n/a"
            print(
                "Memory: avg {} | curr {:5.1f}% ({}/{})".format(
                    mem_avg_str,
                    mem_percent,
                    human_bytes(vm.used),
                    human_bytes(vm.total),
                )
            )

            if avg_disk_read.has_samples():
                disk_avg = "R {} W {}".format(
                    human_bytes_per_s(avg_disk_read.average()),
                    human_bytes_per_s(avg_disk_write.average()),
                )
            else:
                disk_avg = "n/a"
            if disk_read_rate is not None and disk_write_rate is not None:
                disk_curr = "R {} W {}".format(
                    human_bytes_per_s(disk_read_rate),
                    human_bytes_per_s(disk_write_rate),
                )
            else:
                disk_curr = "n/a"
            print(f"Disk  : avg {disk_avg} | curr {disk_curr}")

            if avg_net_send.has_samples():
                net_avg = "S {} R {}".format(
                    human_bytes_per_s(avg_net_send.average()),
                    human_bytes_per_s(avg_net_recv.average()),
                )
            else:
                net_avg = "n/a"
            if net_send_rate is not None and net_recv_rate is not None:
                net_curr = "S {} R {}".format(
                    human_bytes_per_s(net_send_rate),
                    human_bytes_per_s(net_recv_rate),
                )
            else:
                net_curr = "n/a"
            print(f"Net   : avg {net_avg} | curr {net_curr}")

            gpu_avg_str = f"{avg_gpu.average():5.1f}%" if avg_gpu.has_samples() else "  n/a"
            gpu_curr_str = f"{gpu_now:5.1f}%" if gpu_now is not None else "  n/a"
            gpu_top_str = format_top_list(gpu_top) if gpu_top else "n/a"
            print(f"GPUComp: avg {gpu_avg_str} | curr {gpu_curr_str} | top {gpu_top_str}")  # Compute使用率を表示

            # NPU/AI活動の表示
            if npu_now is not None:
                # PDH カウンターからの直接値がある場合
                npu_curr_str = f"{npu_now:5.1f}%"
                npu_status = ""
            elif npu_estimated != "n/a":
                # AI活動からの推定値がある場合
                npu_curr_str = npu_estimated
                npu_status = " (AI-estimated)"
            else:
                # 何も検出されない場合
                npu_curr_str = "  n/a"
                npu_status = ""
            
            # Intel AI Boost検出状況を含めた詳細表示
            if intel_ai_boost_detected and npu_reader is None:
                if current_ai_activity['active']:
                    npu_status += f" (Intel AI Boost, {ai_status})"
                else:
                    npu_status += " (Intel AI Boost detected, no PDH counter)"
            elif intel_ai_boost_detected:
                npu_status += " (Intel AI Boost available)"
            elif npu_reader is None:
                if current_ai_activity['active']:
                    npu_status += f" ({ai_status})"
                else:
                    npu_status += " (no NPU counter available)"
            
            npu_avg_str = f"{avg_npu.average():5.1f}%" if avg_npu.has_samples() else "  n/a"
            npu_top_str = format_top_list(npu_top) if npu_top else "n/a"
            
            print(f"NPU   : avg {npu_avg_str} | curr {npu_curr_str} | top {npu_top_str}{npu_status}")



            last_sample_ts = loop_start
            time.sleep(REFRESH_SEC)

        except KeyboardInterrupt:
            break

    # クリーンアップ
    ai_detector.stop_monitoring()

if __name__ == "__main__":
    main()
