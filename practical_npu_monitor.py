#!/usr/bin/env python3
"""
Intel AI Boost NPU 実用監視スクリプト
直接的なNPUカウンタが利用できない環境での実用的なNPU活動監視
"""

import time
import psutil
import math
from collections import deque, defaultdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime

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

class IntelAIBoostMonitor:
    """Intel AI Boost NPU用実用監視クラス"""
    
    def __init__(self):
        self.ai_boost_detected = self._detect_ai_boost()
        
        # 利用可能なカウンタを設定
        self.power_counters = self._setup_power_counters()
        self.processor_counters = self._setup_processor_counters()
        self.gpu_counters = self._setup_gpu_counters()
        
        # 統計データ
        self.cpu_baseline = deque(maxlen=120)  # 2分間のベースライン
        self.ai_activity_history = deque(maxlen=300)  # 5分間の履歴
        self.power_history = deque(maxlen=300)
        
        # AI プロセス検出
        self.ai_patterns = [
            'onnxruntime', 'directml', 'pytorch', 'tensorflow',
            'windowsai', 'winml', 'copilot', 'chatgpt'
        ]
        
        print("Intel AI Boost NPU Monitor Initialized")
        print(f"  NPU Hardware: {'✓ Detected' if self.ai_boost_detected else '✗ Not detected'}")
        print(f"  Power Counters: {'✓ Available' if self.power_counters else '✗ Not available'}")
        print(f"  GPU Counters: {'✓ Available' if self.gpu_counters else '✗ Not available'}")
        print()
    
    def _detect_ai_boost(self) -> bool:
        """Intel AI Boost検出"""
        if not HAS_WMI:
            return False
        
        try:
            c = wmi.WMI()
            for device in c.Win32_PnPEntity():
                if 'Intel(R) AI Boost' in str(getattr(device, 'Name', '')):
                    return True
        except:
            pass
        return False
    
    def _setup_power_counters(self) -> Optional[object]:
        """電力カウンタ設定"""
        if not HAS_PDH:
            return None
        
        try:
            query = win32pdh.OpenQuery()
            counter = win32pdh.AddCounter(query, r"\Power Meter(_Total)\Power")
            win32pdh.CollectQueryData(query)
            return (query, counter)
        except:
            return None
    
    def _setup_processor_counters(self) -> List[Tuple]:
        """プロセッサーカウンタ設定（主要コア用）"""
        if not HAS_PDH:
            return []
        
        counters = []
        try:
            query = win32pdh.OpenQuery()
            
            # 主要なプロセッサーメトリクス
            patterns = [
                r"\Processor Information(_Total)\% Processor Utility",
                r"\Processor Information(_Total)\% Performance Limit",
                r"\Processor Information(_Total)\Actual Frequency"
            ]
            
            for pattern in patterns:
                try:
                    counter = win32pdh.AddCounter(query, pattern)
                    counters.append((counter, pattern))
                except:
                    continue
            
            if counters:
                win32pdh.CollectQueryData(query)
                return (query, counters)
        except:
            pass
        return []
    
    def _setup_gpu_counters(self) -> Optional[object]:
        """GPU Computeエンジンカウンタ設定"""
        if not HAS_PDH:
            return None
        
        try:
            # GPU Computeエンジンを探す
            paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*)\Utilization Percentage")
            compute_paths = [p for p in paths if 'compute' in p.lower() or 'engtype_3d' in p.lower()]
            
            if not compute_paths:
                return None
            
            query = win32pdh.OpenQuery()
            counters = []
            
            for path in compute_paths[:5]:  # 最初の5個のみ
                try:
                    counter = win32pdh.AddCounter(query, path)
                    counters.append((counter, path))
                except:
                    continue
            
            if counters:
                win32pdh.CollectQueryData(query)
                return (query, counters)
        except:
            pass
        return None
    
    def get_power_usage(self) -> Optional[float]:
        """システム電力使用量を取得"""
        if not self.power_counters:
            return None
        
        try:
            query, counter = self.power_counters
            time.sleep(0.1)
            win32pdh.CollectQueryData(query)
            t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
            return val if not math.isnan(val) else None
        except:
            return None
    
    def get_processor_metrics(self) -> Dict[str, float]:
        """プロセッサーメトリクス取得"""
        if not self.processor_counters:
            return {}
        
        try:
            query, counters = self.processor_counters
            time.sleep(0.1)
            win32pdh.CollectQueryData(query)
            
            metrics = {}
            for counter, pattern in counters:
                try:
                    t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
                    if not math.isnan(val):
                        # パターンから名前を抽出
                        name = pattern.split('\\')[-1]
                        metrics[name] = val
                except:
                    continue
            
            return metrics
        except:
            return {}
    
    def get_gpu_compute_usage(self) -> float:
        """GPU Compute使用率取得"""
        if not self.gpu_counters:
            return 0.0
        
        try:
            query, counters = self.gpu_counters
            time.sleep(0.1)
            win32pdh.CollectQueryData(query)
            
            usages = []
            for counter, path in counters:
                try:
                    t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
                    if not math.isnan(val) and val >= 0:
                        usages.append(val)
                except:
                    continue
            
            return max(usages) if usages else 0.0
        except:
            return 0.0
    
    def detect_ai_processes(self) -> List[Dict]:
        """AI関連プロセス検出"""
        ai_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    for pattern in self.ai_patterns:
                        if pattern in proc_name:
                            ai_processes.append({
                                'pid': proc.info['pid'],
                                'name': proc.info['name'],
                                'type': pattern,
                                'cpu_percent': proc.info['cpu_percent'] or 0,
                                'memory_percent': proc.info['memory_percent'] or 0
                            })
                            break
                    else:
                        # Pythonプロセスのコマンドライン確認
                        if 'python' in proc_name:
                            try:
                                cmdline = ' '.join(proc.cmdline()).lower()
                                if any(kw in cmdline for kw in ['onnx', 'torch', 'ml', 'ai']):
                                    ai_processes.append({
                                        'pid': proc.info['pid'],
                                        'name': proc.info['name'],
                                        'type': 'python_ai',
                                        'cpu_percent': proc.info['cpu_percent'] or 0,
                                        'memory_percent': proc.info['memory_percent'] or 0
                                    })
                            except:
                                pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except:
            pass
        
        return ai_processes
    
    def estimate_npu_activity(self, ai_processes: List[Dict], power_usage: Optional[float], 
                             gpu_usage: float, cpu_percent: float) -> Dict[str, float]:
        """NPU活動推定"""
        ai_active = len(ai_processes) > 0
        
        # 履歴更新
        self.ai_activity_history.append((time.time(), ai_active, len(ai_processes)))
        if power_usage:
            self.power_history.append((time.time(), power_usage))
        
        # ベースライン更新
        if not ai_active:
            self.cpu_baseline.append(cpu_percent)
        
        # NPU活動推定
        npu_estimate = 0.0
        confidence = 0
        
        if ai_active and len(self.cpu_baseline) > 30:
            baseline_cpu = sum(self.cpu_baseline) / len(self.cpu_baseline)
            cpu_efficiency = max(0, (baseline_cpu - cpu_percent) / baseline_cpu) if baseline_cpu > 0 else 0
            
            # GPU使用率が低いのにAI処理が動いている場合、NPU使用の可能性
            if cpu_efficiency > 0.1 and gpu_usage < 20:  # CPU効率化 + GPU使用率低
                npu_estimate = min(100, cpu_efficiency * 200)
                confidence = min(100, cpu_efficiency * 300 + 20)
            elif gpu_usage > 50:  # GPU高使用率の場合
                npu_estimate = 0
                confidence = 80  # GPU使用でNPU使用なしの信頼度
        
        return {
            'npu_usage_estimate': npu_estimate,
            'confidence': confidence,
            'ai_active': ai_active,
            'ai_process_count': len(ai_processes)
        }
    
    def display_status(self, metrics: Dict):
        """ステータス表示"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        print(f"[{timestamp}] Intel AI Boost NPU Status")
        print("-" * 60)
        
        # NPU推定
        npu_est = metrics.get('npu_estimate', {})
        npu_usage = npu_est.get('npu_usage_estimate', 0)
        confidence = npu_est.get('confidence', 0)
        
        if npu_usage > 0:
            print(f"NPU Activity : {npu_usage:5.1f}% (estimated, confidence: {confidence:.0f}%)")
        else:
            print("NPU Activity :   0.0% (no significant activity detected)")
        
        # AI プロセス
        ai_processes = metrics.get('ai_processes', [])
        if ai_processes:
            total_ai_cpu = sum(p['cpu_percent'] for p in ai_processes)
            print(f"AI Processes : {len(ai_processes)} active (total CPU: {total_ai_cpu:.1f}%)")
            for proc in ai_processes[:2]:  # 最初の2つ
                print(f"  └─ {proc['name']} ({proc['type']}) - {proc['cpu_percent']:.1f}% CPU")
        else:
            print("AI Processes : None detected")
        
        # システムメトリクス
        cpu_percent = metrics.get('cpu_percent', 0)
        gpu_usage = metrics.get('gpu_usage', 0)
        power_usage = metrics.get('power_usage')
        
        print(f"System       : CPU {cpu_percent:4.1f}%, GPU Compute {gpu_usage:4.1f}%", end="")
        if power_usage:
            print(f", Power {power_usage:5.1f}W")
        else:
            print()
        
        # プロセッサー詳細
        proc_metrics = metrics.get('processor_metrics', {})
        if proc_metrics:
            util = proc_metrics.get('% Processor Utility', 0)
            freq = proc_metrics.get('Actual Frequency', 0)
            limit = proc_metrics.get('% Performance Limit', 0)
            print(f"Processor    : Utility {util:.1f}%, Freq {freq:.0f}MHz, Limit {limit:.1f}%")
        
        print()
    
    def start_monitoring(self):
        """監視開始"""
        print("Starting Intel AI Boost NPU monitoring...")
        print("Note: Using indirect monitoring methods due to lack of direct NPU counters")
        print("Press Ctrl+C to stop\n")
        
        # CPU初期化
        psutil.cpu_percent(interval=None)
        
        try:
            while True:
                # データ収集
                cpu_percent = psutil.cpu_percent(interval=None)
                ai_processes = self.detect_ai_processes()
                power_usage = self.get_power_usage()
                gpu_usage = self.get_gpu_compute_usage()
                processor_metrics = self.get_processor_metrics()
                
                # NPU活動推定
                npu_estimate = self.estimate_npu_activity(ai_processes, power_usage, gpu_usage, cpu_percent)
                
                # メトリクス統合
                metrics = {
                    'cpu_percent': cpu_percent,
                    'ai_processes': ai_processes,
                    'power_usage': power_usage,
                    'gpu_usage': gpu_usage,
                    'processor_metrics': processor_metrics,
                    'npu_estimate': npu_estimate
                }
                
                # 表示
                self.display_status(metrics)
                
                time.sleep(2.0)  # 2秒間隔
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            self._print_summary()
    
    def _print_summary(self):
        """監視サマリー表示"""
        if not self.ai_activity_history:
            return
        
        ai_active_count = sum(1 for _, active, _ in self.ai_activity_history if active)
        ai_ratio = ai_active_count / len(self.ai_activity_history) * 100
        
        print(f"\nSession Summary:")
        print(f"  AI Activity: {ai_ratio:.1f}% of time ({ai_active_count}/{len(self.ai_activity_history)} samples)")
        
        if self.power_history:
            powers = [p for _, p in self.power_history]
            print(f"  Power Usage: Avg {sum(powers)/len(powers):.1f}W, Max {max(powers):.1f}W")

def main():
    """メイン関数"""
    print("Intel AI Boost NPU Practical Monitor")
    print("Monitoring NPU activity using indirect methods")
    print()
    
    monitor = IntelAIBoostMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main()