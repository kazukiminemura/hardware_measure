#!/usr/bin/env python3
"""
Simple NPU Monitor - シンプルなNPU専用監視スクリプト
NPUエンジンと AI推論活動の基本的な監視
"""

import time
import psutil
import math
from collections import deque
from typing import Dict, List, Optional
from datetime import datetime

# ----- Optional Dependencies -----
try:
    import win32pdh
    HAS_PDH = True
except ImportError:
    HAS_PDH = False

try:
    import wmi
    HAS_WMI = True
except ImportError:
    HAS_WMI = False

REFRESH_SEC = 1.0

class SimpleNPUMonitor:
    """シンプルなNPU監視クラス"""
    
    def __init__(self):
        # NPU検出
        self.intel_ai_boost_detected = self._detect_intel_ai_boost()
        self.npu_counters_available = self._check_npu_counters()
        
        # NPU Performance Counters
        self.npu_query = None
        self.npu_counters = []
        if self.npu_counters_available:
            self._setup_npu_counters()
        
        # 統計用
        self.cpu_baseline = deque(maxlen=60)  # 1分間のベースライン
        self.ai_cpu_usage = deque(maxlen=60)  # AI使用時のCPU
        
        # AI プロセスパターン
        self.ai_patterns = [
            'onnxruntime', 'directml', 'pytorch', 'tensorflow',
            'python', 'copilot', 'windowsai', 'winml'
        ]
        
        # セッション統計
        self.session_start = time.time()
        self.ai_detection_count = 0
        self.total_samples = 0
    
    def _detect_intel_ai_boost(self) -> bool:
        """Intel AI Boost NPUを検出"""
        if not HAS_WMI:
            return False
        
        try:
            c = wmi.WMI()
            for device in c.Win32_PnPEntity():
                device_name = str(getattr(device, 'Name', ''))
                if 'Intel(R) AI Boost' in device_name:
                    return True
        except Exception:
            pass
        return False
    
    def _check_npu_counters(self) -> bool:
        """NPU Performance Countersをチェック"""
        if not HAS_PDH:
            return False
        
        try:
            paths = win32pdh.ExpandCounterPath(r"\NPU Engine(*)\Utilization Percentage")
            return bool(paths)
        except Exception:
            return False
    
    def _setup_npu_counters(self):
        """NPU Countersセットアップ"""
        try:
            paths = win32pdh.ExpandCounterPath(r"\NPU Engine(*)\Utilization Percentage")
            self.npu_query = win32pdh.OpenQuery()
            
            for path in paths:
                try:
                    handle = win32pdh.AddCounter(self.npu_query, path)
                    self.npu_counters.append((handle, path))
                except Exception:
                    continue
            
            if self.npu_counters:
                win32pdh.CollectQueryData(self.npu_query)
        except Exception:
            self.npu_counters_available = False
    
    def get_npu_usage(self) -> float:
        """NPU使用率を取得"""
        if not self.npu_counters_available or not self.npu_counters:
            return -1  # 利用不可
        
        try:
            time.sleep(0.1)
            win32pdh.CollectQueryData(self.npu_query)
            
            usage_values = []
            for handle, path in self.npu_counters:
                try:
                    t, val = win32pdh.GetFormattedCounterValue(handle, win32pdh.PDH_FMT_DOUBLE)
                    if not math.isnan(val) and val >= 0:
                        usage_values.append(val)
                except Exception:
                    continue
            
            return max(usage_values) if usage_values else 0
        except Exception:
            return -1
    
    def detect_ai_processes(self) -> List[Dict]:
        """AI関連プロセスを検出"""
        ai_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # 基本的なAI プロセス検出
                    for pattern in self.ai_patterns:
                        if pattern in proc_name:
                            ai_type = pattern
                            break
                    else:
                        # Pythonプロセスの場合、コマンドライン確認
                        if 'python' in proc_name:
                            try:
                                cmdline = ' '.join(proc.cmdline()).lower()
                                if any(kw in cmdline for kw in ['onnx', 'torch', 'ml', 'ai']):
                                    ai_type = 'python_ai'
                                else:
                                    continue
                            except:
                                continue
                        else:
                            continue
                    
                    ai_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'type': ai_type,
                        'cpu_percent': proc.info['cpu_percent'] or 0
                    })
                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return ai_processes
    
    def estimate_npu_from_cpu(self, current_cpu: float, ai_active: bool) -> Optional[float]:
        """CPU使用パターンからNPU使用率を推定"""
        if ai_active:
            self.ai_cpu_usage.append(current_cpu)
        else:
            self.cpu_baseline.append(current_cpu)
        
        # 十分なデータがない場合
        if len(self.cpu_baseline) < 20 or len(self.ai_cpu_usage) < 10:
            return None
        
        baseline_avg = sum(self.cpu_baseline) / len(self.cpu_baseline)
        ai_avg = sum(self.ai_cpu_usage) / len(self.ai_cpu_usage)
        
        if baseline_avg <= 0:
            return None
        
        # CPU負荷軽減率
        cpu_reduction = max(0, (baseline_avg - ai_avg) / baseline_avg)
        
        # NPU使用率推定（15%以上の軽減でNPU使用とみなす）
        if cpu_reduction > 0.15:
            return min(100, cpu_reduction * 200)  # 軽減率の2倍を推定値
        else:
            return 0
    
    def print_status(self):
        """NPU検出状況を表示"""
        print("=" * 60)
        print(" Simple NPU Monitor - Status")
        print("=" * 60)
        
        if self.intel_ai_boost_detected:
            print("✓ Intel AI Boost NPU: Detected")
        else:
            print("✗ Intel AI Boost NPU: Not detected")
        
        if self.npu_counters_available:
            print(f"✓ NPU Performance Counters: Available ({len(self.npu_counters)} counters)")
        else:
            print("✗ NPU Performance Counters: Not available")
        
        print(f"✓ AI Process Detection: Enabled")
        print(f"✓ CPU-based NPU Estimation: Enabled")
        print()
    
    def start_monitoring(self):
        """監視を開始"""
        self.print_status()
        
        print("Starting Simple NPU Monitoring...")
        print("Press Ctrl+C to stop\n")
        
        # CPU初期化
        psutil.cpu_percent(interval=None)
        
        try:
            while True:
                self.total_samples += 1
                
                # データ収集
                cpu_percent = psutil.cpu_percent(interval=None)
                memory_percent = psutil.virtual_memory().percent
                ai_processes = self.detect_ai_processes()
                ai_active = len(ai_processes) > 0
                
                if ai_active:
                    self.ai_detection_count += 1
                
                # NPU使用率
                npu_direct = self.get_npu_usage()
                npu_estimated = self.estimate_npu_from_cpu(cpu_percent, ai_active)
                
                # 表示
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] ", end="")
                
                # NPU使用率表示
                if npu_direct >= 0:
                    print(f"NPU: {npu_direct:5.1f}% (direct) ", end="")
                else:
                    print("NPU:   n/a (direct) ", end="")
                
                if npu_estimated is not None:
                    print(f"Est: {npu_estimated:5.1f}% ", end="")
                else:
                    print("Est:   n/a ", end="")
                
                # AI活動
                if ai_active:
                    ai_cpu_total = sum(p['cpu_percent'] for p in ai_processes)
                    print(f"| AI: {len(ai_processes)} proc ({ai_cpu_total:4.1f}% CPU) ", end="")
                else:
                    print("| AI: inactive ", end="")
                
                # システムリソース
                print(f"| Sys: CPU {cpu_percent:4.1f}%, Mem {memory_percent:4.1f}%")
                
                # 詳細表示（AI プロセスがある場合）
                if ai_processes and len(ai_processes) <= 3:
                    for proc in ai_processes:
                        print(f"    └─ {proc['name']} (PID:{proc['pid']}) - "
                              f"{proc['cpu_percent']:.1f}% CPU ({proc['type']})")
                
                time.sleep(REFRESH_SEC)
                
        except KeyboardInterrupt:
            self._print_final_summary()
    
    def _print_final_summary(self):
        """最終サマリー表示"""
        session_duration = time.time() - self.session_start
        ai_activity_ratio = (self.ai_detection_count / self.total_samples * 100) if self.total_samples > 0 else 0
        
        print(f"\n\n{'='*50}")
        print(" Session Summary")
        print(f"{'='*50}")
        print(f"Duration: {session_duration:.0f} seconds")
        print(f"Total samples: {self.total_samples}")
        print(f"AI activity: {ai_activity_ratio:.1f}% of time ({self.ai_detection_count}/{self.total_samples})")
        
        if self.cpu_baseline:
            baseline_avg = sum(self.cpu_baseline) / len(self.cpu_baseline)
            print(f"CPU baseline average: {baseline_avg:.1f}%")
        
        if self.ai_cpu_usage:
            ai_avg = sum(self.ai_cpu_usage) / len(self.ai_cpu_usage)
            print(f"CPU during AI: {ai_avg:.1f}%")
        
        print("\nNPU Detection Status:")
        print(f"  Intel AI Boost: {'Detected' if self.intel_ai_boost_detected else 'Not detected'}")
        print(f"  Performance Counters: {'Available' if self.npu_counters_available else 'Not available'}")

def main():
    """メイン関数"""
    print("Simple NPU Monitor")
    print("Basic NPU engine and AI inference monitoring")
    print()
    
    monitor = SimpleNPUMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main()