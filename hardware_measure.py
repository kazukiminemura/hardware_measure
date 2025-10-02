# monitor_hw_usage.py
import time
import psutil
import math
from collections import defaultdict
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any

# ----- GPU/NPU (PDH) via pywin32 -----
try:
    import win32pdh
    HAS_PDH = True
except Exception:
    HAS_PDH = False

REFRESH_SEC = 1.0

class MetricsCollector(ABC):
    """メトリクス収集の抽象基底クラス"""
    
    @abstractmethod
    def collect(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass

class RunningAverage:
    """効率的な累積平均計算"""
    def __init__(self):
        self._total = 0.0
        self._count = 0

    def add(self, value: Optional[float]) -> None:
        if value is not None:
            self._total += float(value)
            self._count += 1

    def has_samples(self) -> bool:
        return self._count > 0

    def average(self) -> float:
        return self._total / self._count if self._count else 0.0

class PDHCollector(MetricsCollector):
    """PDH (Performance Data Helper) メトリクスコレクター"""
    
    def __init__(self, path_pattern: str, include_names: List[str] = None, exclude_contains: List[str] = None):
        self.path_pattern = path_pattern
        self.include_names = include_names or []
        self.exclude_contains = exclude_contains or []
        self.query = None
        self.counters = []
        self._available = False
        self._try_build()
    
    def _try_build(self) -> None:
        if not HAS_PDH:
            return
        try:
            paths = win32pdh.ExpandCounterPath(self.path_pattern)
            if not paths:
                return
            
            self.query = win32pdh.OpenQuery()
            self.counters = []
            for p in paths:
                try:
                    h = win32pdh.AddCounter(self.query, p)
                    self.counters.append((h, p))
                except Exception:
                    pass
            
            if self.counters:
                win32pdh.CollectQueryData(self.query)
                self._available = True
        except Exception:
            pass

    def is_available(self) -> bool:
        return self._available

    def collect(self) -> Dict[str, Any]:
        if not self._available:
            return {}
        
        try:
            time.sleep(0.2)
            win32pdh.CollectQueryData(self.query)
            data = {}
            
            for h, p in self.counters:
                try:
                    t, val = win32pdh.GetFormattedCounterValue(h, win32pdh.PDH_FMT_DOUBLE)
                    inst = p[p.find('(')+1:p.find(')')] if '(' in p and ')' in p else p
                    data[inst] = float(val)
                except Exception:
                    pass
            
            return self._filter_data(data)
        except Exception:
            return {}
    
    def _filter_data(self, data: Dict[str, float]) -> Dict[str, float]:
        """
        エンジンデータをフィルタリングする
        
        Args:
            data: 生のエンジンデータ (インスタンス名 -> 使用率)
            
        Returns:
            フィルタリング済みのデータ
        """
        filtered = {}
        for name, value in data.items():
            # include_namesが指定されている場合、そのキーワードを含むもののみ
            if self.include_names and not any(tag.lower() in name.lower() for tag in self.include_names):
                continue
            
            # exclude_containsが指定されている場合、そのキーワードを含むものを除外
            if self.exclude_contains and any(tag.lower() in name.lower() for tag in self.exclude_contains):
                continue
            
            # 無効・NaNを除外
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(numeric) or numeric < 0:
                continue
            
            filtered[name] = numeric
        return filtered

class SystemCollector(MetricsCollector):
    """システムメトリクス（CPU、メモリ、ディスク、ネットワーク）コレクター"""
    
    def __init__(self):
        self.last_disk_io = None
        self.last_net_io = None
        self.last_sample_ts = time.monotonic()
    
    def is_available(self) -> bool:
        return True
    
    def collect(self) -> Dict[str, Any]:
        current_time = time.monotonic()
        elapsed = max(current_time - self.last_sample_ts, 1e-6)
        
        # CPU & Memory
        cpu_overall = psutil.cpu_percent(interval=None)
        cpu_per = psutil.cpu_percent(interval=None, percpu=True)
        vm = psutil.virtual_memory()
        
        # Disk I/O
        disk_io = psutil.disk_io_counters()
        disk_read_rate = disk_write_rate = None
        if self.last_disk_io:
            disk_read_rate = max(0.0, disk_io.read_bytes - self.last_disk_io.read_bytes) / elapsed
            disk_write_rate = max(0.0, disk_io.write_bytes - self.last_disk_io.write_bytes) / elapsed
        self.last_disk_io = disk_io
        
        # Network I/O
        net_io = psutil.net_io_counters()
        net_send_rate = net_recv_rate = None
        if self.last_net_io:
            net_send_rate = max(0.0, net_io.bytes_sent - self.last_net_io.bytes_sent) / elapsed
            net_recv_rate = max(0.0, net_io.bytes_recv - self.last_net_io.bytes_recv) / elapsed
        self.last_net_io = net_io
        
        self.last_sample_ts = current_time
        
        return {
            'cpu_overall': cpu_overall,
            'cpu_per_core': cpu_per,
            'memory_percent': vm.percent,
            'memory_used': vm.used,
            'memory_total': vm.total,
            'disk_read_rate': disk_read_rate,
            'disk_write_rate': disk_write_rate,
            'net_send_rate': net_send_rate,
            'net_recv_rate': net_recv_rate
        }

class UtilityFunctions:
    """ユーティリティ関数群"""
    
    @staticmethod
    def summarize_engine_util(data: Dict[str, float], include_names: List[str] = None) -> Tuple[float, List[Tuple[str, float]]]:
        """
        PDHのGPU/NPU Engine*(インスタンス)を集計。
        
        Args:
            data: エンジンデータ (インスタンス名 -> 使用率)
            include_names: サマリに含めたいキーワード（例: ['Compute', '3D']）
            
        Returns:
            (overall_percent, top5_list): 全体使用率とトップ5のリスト
        """
        if not data:
            return (0.0, [])
        
        # データの有効性チェック
        filtered = {}
        for name, value in data.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(numeric) or numeric < 0:
                continue
            filtered[name] = numeric
        
        if not filtered:
            return (0.0, [])
        
        # トップ5のリストを作成
        top = sorted(filtered.items(), key=lambda item: item[1], reverse=True)[:5]
        
        # Compute Engine専用の場合、より精密な計算
        if include_names and any(name.lower() in ['compute', 'engtype_compute'] for name in include_names):
            # Compute Engineの場合、最大値を採用（並列処理を考慮）
            overall = max(filtered.values()) if filtered else 0.0
        else:
            # 従来通りの平均値計算
            overall = sum(val for _, val in top) / len(top) if top else 0.0
        
        return (overall, top)
    
    @staticmethod
    def format_top_list(top_list: List[Tuple[str, float]], max_items: int = 5) -> str:
        return ", ".join([f"{k}:{v:.0f}%" for k, v in top_list[:max_items]])
    
    @staticmethod
    def human_bytes(n: Optional[float]) -> str:
        if n is None:
            return "n/a"
        units = ['B','KB','MB','GB','TB']
        i, f = 0, float(n)
        while f >= 1024 and i < len(units)-1:
            f /= 1024.0
            i += 1
        return f"{f:.1f}{units[i]}"
    
    @staticmethod
    def human_bytes_per_s(n: Optional[float]) -> str:
        if n is None:
            return "n/a"
        units = ['B/s','KB/s','MB/s','GB/s','TB/s']
        i, f = 0, float(n)
        while f >= 1024 and i < len(units)-1:
            f /= 1024.0
            i += 1
        return f"{f:.1f}{units[i]}"

class NPUDetector:
    """NPUデバイス検出クラス"""
    
    @staticmethod
    def detect_intel_ai_boost() -> bool:
        """Intel AI Boost NPUを検出"""
        try:
            import wmi
            c = wmi.WMI()
            devices = c.Win32_PnPEntity()
            for device in devices:
                device_name = str(getattr(device, 'Name', ''))
                if 'Intel(R) AI Boost' in device_name:
                    return True
        except Exception:
            pass
        return False
    
    @staticmethod
    def check_npu_counters() -> bool:
        """NPU Performance Countersの利用可能性をチェック"""
        try:
            import win32pdh
            paths = win32pdh.ExpandCounterPath(r"\NPU Engine(*)\Utilization Percentage")
            return bool(paths)
        except Exception:
            return False
    
    @staticmethod
    def print_npu_status():
        """NPU検出状況を表示"""
        print("NPU Detection Status:")
        print("-" * 40)
        
        intel_ai_boost_found = NPUDetector.detect_intel_ai_boost()
        if intel_ai_boost_found:
            print("✓ Intel AI Boost NPU detected")
        else:
            print("✗ Intel AI Boost NPU not detected")
        
        npu_counters_available = NPUDetector.check_npu_counters()
        if npu_counters_available:
            print("✓ NPU Performance Counters available")
        else:
            print("✗ NPU Performance Counters not available")
            if intel_ai_boost_found:
                print("    → Intel AI Boost NPU detected but PDH counters are not exposed")
                print("    → This is common on current Windows versions")
        
        if intel_ai_boost_found:
            print("\nCURRENT STATUS:")
            print("  - NPU hardware: ✓ Detected (Intel AI Boost)")
            print("  - PDH counters: ✗ Not available (expected on most systems)")
        else:
            print("\nNOTE: No NPU detected on this system")
        
        print()  # 空行


class HardwareMonitor:
    """ハードウェア監視のメインクラス"""
    
    def __init__(self):
        self.system_collector = SystemCollector()
        # GPU監視：Computeエンジンのみを対象とし、Copy/Video/3Dを除外
        self.gpu_collector = PDHCollector(
            r"\GPU Engine(*)\Utilization Percentage",
            include_names=["Compute"],  # Computeエンジンのみを対象
            exclude_contains=["Copy", "Video", "3D"]  # Copy, Video, 3D系を除外
        )
        self.npu_collector = PDHCollector(r"\NPU Engine(*)\Utilization Percentage")
        
        # 統計計算用
        self.averages = {
            'cpu': RunningAverage(),
            'memory': RunningAverage(),
            'gpu': RunningAverage(),
            'npu': RunningAverage(),
            'disk_read': RunningAverage(),
            'disk_write': RunningAverage(),
            'net_send': RunningAverage(),
            'net_recv': RunningAverage()
        }
        
        # NPU検出情報
        self.intel_ai_boost_detected = NPUDetector.detect_intel_ai_boost()
        
        # GPU監視の可用性チェック
        self._gpu_available = self.gpu_collector.is_available()
        if not self._gpu_available:
            print("Warning: GPU Performance Counters not available - GPU monitoring disabled")
    
    def get_gpu_usage(self) -> Tuple[float, List[Tuple[str, float]]]:
        """
        GPU Compute使用率を取得
        
        Returns:
            (overall_percent, top_engines): 全体使用率とトップエンジンのリスト
        """
        if not self._gpu_available:
            return (0.0, [])
        
        try:
            gpu_data = self.gpu_collector.collect()
            if not gpu_data:
                return (0.0, [])
            
            # Compute Engineの使用率を計算
            overall, top = UtilityFunctions.summarize_engine_util(
                gpu_data, 
                include_names=["Compute"]  # Computeエンジンのみ
            )
            
            # 値を0-100の範囲にクランプ
            clamped_overall = max(0.0, min(100.0, overall))
            clamped_top = [(name, max(0.0, min(100.0, val))) for name, val in top]
            
            return (clamped_overall, clamped_top)
            
        except Exception as e:
            print(f"GPU monitoring error: {e}")
            return (0.0, [])
    
    def get_gpu_detailed_info(self) -> Dict[str, Any]:
        """
        詳細なGPU利用情報を取得（フロントエンド表示用）
        
        Returns:
            GPU利用状況の詳細情報
        """
        if not self._gpu_available:
            return {
                "available": False,
                "compute_percent": 0.0,
                "overall_percent": 0.0,
                "engines": {},
                "top_engines": [],
                "compute_engines": [],
                "method": "pdh_unavailable"
            }
        
        try:
            gpu_data = self.gpu_collector.collect()
            if not gpu_data:
                return {
                    "available": True,
                    "compute_percent": 0.0,
                    "overall_percent": 0.0,
                    "engines": {},
                    "top_engines": [],
                    "compute_engines": [],
                    "method": "pdh_no_data"
                }
            
            # Compute Engine使用率
            compute_overall, compute_top = UtilityFunctions.summarize_engine_util(
                gpu_data,
                include_names=["Compute"]
            )
            
            # 全体GPU使用率（Copy除く）
            overall_data = {k: v for k, v in gpu_data.items() 
                          if not any(exclude.lower() in k.lower() for exclude in ["Copy"])}
            overall_percent, overall_top = UtilityFunctions.summarize_engine_util(overall_data)
            
            # 値をクランプ
            def clamp(value: float) -> float:
                return max(0.0, min(100.0, float(value)))
            
            return {
                "available": True,
                "compute_percent": clamp(compute_overall),
                "overall_percent": clamp(overall_percent),
                "engines": {name: clamp(val) for name, val in gpu_data.items()},
                "top_engines": [(name, clamp(val)) for name, val in overall_top[:3]],
                "compute_engines": [(name, clamp(val)) for name, val in compute_top[:3]],
                "method": "pdh"
            }
            
        except Exception as e:
            print(f"Detailed GPU monitoring error: {e}")
            return {
                "available": False,
                "compute_percent": 0.0,
                "overall_percent": 0.0,
                "engines": {},
                "top_engines": [],
                "compute_engines": [],
                "method": "error"
            }
    
    def start_monitoring(self):
        """監視開始"""
        self.print_header()
        NPUDetector.print_npu_status()
        
        psutil.cpu_percent(interval=None)  # CPU priming
        
        try:
            while True:
                self.collect_and_display_metrics()
                time.sleep(REFRESH_SEC)
        except KeyboardInterrupt:
            pass
    
    def collect_and_display_metrics(self):
        """メトリクス収集と表示"""
        # システムメトリクス収集
        sys_data = self.system_collector.collect()
        gpu_data = self.gpu_collector.collect()
        npu_data = self.npu_collector.collect()
        
        # 統計更新
        self.update_averages(sys_data, gpu_data, npu_data)
        
        # 表示
        self.display_metrics(sys_data, gpu_data, npu_data)
    
    def update_averages(self, sys_data: Dict, gpu_data: Dict, npu_data: Dict):
        """平均値を更新"""
        self.averages['cpu'].add(sys_data['cpu_overall'])
        self.averages['memory'].add(sys_data['memory_percent'])
        
        if sys_data['disk_read_rate'] is not None:
            self.averages['disk_read'].add(sys_data['disk_read_rate'])
            self.averages['disk_write'].add(sys_data['disk_write_rate'])
        
        if sys_data['net_send_rate'] is not None:
            self.averages['net_send'].add(sys_data['net_send_rate'])
            self.averages['net_recv'].add(sys_data['net_recv_rate'])
        
        # 改良されたGPU使用率計算を使用
        if self._gpu_available:
            gpu_overall, _ = self.get_gpu_usage()
            self.averages['gpu'].add(gpu_overall)
        
        if npu_data:
            npu_overall, _ = UtilityFunctions.summarize_engine_util(npu_data)
            self.averages['npu'].add(npu_overall)
    
    def display_metrics(self, sys_data: Dict, gpu_data: Dict, npu_data: Dict):
        """メトリクス表示"""
        print("\n" + "-"*78)
        
        # CPU
        cpu_avg = f"{self.averages['cpu'].average():5.1f}%" if self.averages['cpu'].has_samples() else "  n/a"
        cpu_cores = ", ".join(f"{p:4.0f}%" for p in sys_data['cpu_per_core'])
        print(f"CPU   : avg {cpu_avg} | curr {sys_data['cpu_overall']:5.1f}% | per-core: {cpu_cores}")
        
        # Memory
        mem_avg = f"{self.averages['memory'].average():5.1f}%" if self.averages['memory'].has_samples() else "  n/a"
        mem_used = UtilityFunctions.human_bytes(sys_data['memory_used'])
        mem_total = UtilityFunctions.human_bytes(sys_data['memory_total'])
        print(f"Memory: avg {mem_avg} | curr {sys_data['memory_percent']:5.1f}% ({mem_used}/{mem_total})")
        
        # Disk
        disk_avg = self.format_disk_net_avg('disk')
        disk_curr = self.format_disk_curr(sys_data['disk_read_rate'], sys_data['disk_write_rate'])
        print(f"Disk  : avg {disk_avg} | curr {disk_curr}")
        
        # Network
        net_avg = self.format_disk_net_avg('net')
        net_curr = self.format_net_curr(sys_data['net_send_rate'], sys_data['net_recv_rate'])
        print(f"Net   : avg {net_avg} | curr {net_curr}")
        
        # GPU - 改良されたGPU監視を使用
        if self._gpu_available:
            gpu_overall, gpu_top = self.get_gpu_usage()
            gpu_avg = f"{self.averages['gpu'].average():5.1f}%" if self.averages['gpu'].has_samples() else "  n/a"
            gpu_curr = f"{gpu_overall:5.1f}%"
            gpu_top_str = UtilityFunctions.format_top_list(gpu_top) if gpu_top else "n/a"
            print(f"GPUComp: avg {gpu_avg} | curr {gpu_curr} | top {gpu_top_str}")
        else:
            print("GPUComp: n/a (counters not available)")
        
        # NPU
        npu_overall, npu_top = UtilityFunctions.summarize_engine_util(npu_data)
        npu_status = self.format_npu_status(npu_overall)
        npu_avg = f"{self.averages['npu'].average():5.1f}%" if self.averages['npu'].has_samples() else "  n/a"
        npu_curr = f"{npu_overall:5.1f}%" if npu_data else "  n/a"
        npu_top_str = UtilityFunctions.format_top_list(npu_top) if npu_top else "n/a"
        print(f"NPU   : avg {npu_avg} | curr {npu_curr} | top {npu_top_str}{npu_status}")
    
    def format_disk_net_avg(self, type_name: str) -> str:
        """ディスク/ネットワークの平均値をフォーマット"""
        if type_name == 'disk':
            read_avg, write_avg = self.averages['disk_read'], self.averages['disk_write']
            prefix = "R"
        else:
            read_avg, write_avg = self.averages['net_send'], self.averages['net_recv']
            prefix = "S"
        
        if read_avg.has_samples():
            return f"{prefix} {UtilityFunctions.human_bytes_per_s(read_avg.average())} W {UtilityFunctions.human_bytes_per_s(write_avg.average())}"
        return "n/a"
    
    def format_disk_curr(self, read_rate: Optional[float], write_rate: Optional[float]) -> str:
        """ディスクの現在値をフォーマット"""
        if read_rate is not None and write_rate is not None:
            return f"R {UtilityFunctions.human_bytes_per_s(read_rate)} W {UtilityFunctions.human_bytes_per_s(write_rate)}"
        return "n/a"
    
    def format_net_curr(self, send_rate: Optional[float], recv_rate: Optional[float]) -> str:
        """ネットワークの現在値をフォーマット"""
        if send_rate is not None and recv_rate is not None:
            return f"S {UtilityFunctions.human_bytes_per_s(send_rate)} R {UtilityFunctions.human_bytes_per_s(recv_rate)}"
        return "n/a"
    
    def format_npu_status(self, npu_overall: float) -> str:
        """NPUステータスをフォーマット"""
        if npu_overall > 0:
            return ""
        elif self.intel_ai_boost_detected:
            return " (Intel AI Boost detected, no PDH counter)"
        else:
            return " (no NPU counter available)"
    
    def print_header(self):
        """ヘッダー表示"""
        print("="*78)
        print(" Windows Hardware Utilization Monitor (Task Manager-like) ")
        print("="*78)
        print("Ctrl+C to stop\n")

if __name__ == "__main__":
    monitor = HardwareMonitor()
    monitor.start_monitoring()
