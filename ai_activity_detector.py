# AI推論とDirectML活動を検出するためのクラス
import time
import threading
import subprocess
import psutil
from collections import defaultdict, deque

class AIActivityDetector:
    """AI推論活動とDirectML使用を検出・監視"""
    
    def __init__(self):
        self.ai_processes = set()
        self.directml_activity = False
        self.activity_history = deque(maxlen=60)  # 1分間の履歴
        self.monitor_thread = None
        self.monitoring = False
        
        # AI関連プロセス名のパターン
        self.ai_process_patterns = [
            'onnxruntime',
            'DirectML',
            'python',  # Python AI scripts
            'pytorch',
            'tensorflow',
            'windowsai',
            'winml',
            'copilot',
            'recall',  # Windows Recall
            'studio_effects',  # Windows Studio Effects
        ]
        
        # AI関連のDLLパターン
        self.ai_dll_patterns = [
            'directml',
            'onnxruntime',
            'winml',
            'd3d12',
            'dxcore',
        ]
    
    def detect_ai_processes(self):
        """AI関連プロセスを検出"""
        current_ai_processes = set()
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    
                    # プロセス名でのAI関連検出
                    for pattern in self.ai_process_patterns:
                        if pattern in proc_name:
                            current_ai_processes.add((proc_info['pid'], proc_name))
                            break
                    
                    # Pythonプロセスの場合、コマンドラインを確認
                    if 'python' in proc_name:
                        try:
                            cmdline = proc.cmdline()
                            cmdline_str = ' '.join(cmdline).lower()
                            if any(ai_term in cmdline_str for ai_term in ['onnx', 'torch', 'tensorflow', 'ml', 'ai']):
                                current_ai_processes.add((proc_info['pid'], f"{proc_name} (AI)"))
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.ai_processes = current_ai_processes
            return current_ai_processes
            
        except Exception as e:
            print(f"AI プロセス検出エラー: {e}")
            return set()
    
    def check_directml_activity(self):
        """DirectML活動を確認"""
        try:
            # tasklist でDirectML関連プロセスを確認
            result = subprocess.run([
                'tasklist', '/fi', 'imagename eq DirectML*', '/fo', 'csv'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0 and 'DirectML' in result.stdout:
                return True
            
            # DLL使用確認（より高度な検出）
            # このエリアは実装が複雑なため、基本的な検出のみ
            return False
            
        except Exception:
            return False
    
    def start_monitoring(self):
        """AI活動の監視を開始"""
        if self.monitoring:
            return
        
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                try:
                    # AI プロセス検出
                    ai_processes = self.detect_ai_processes()
                    
                    # DirectML 活動確認
                    directml_active = self.check_directml_activity()
                    
                    # 活動記録
                    activity_snapshot = {
                        'timestamp': time.time(),
                        'ai_process_count': len(ai_processes),
                        'directml_active': directml_active,
                        'ai_processes': list(ai_processes)
                    }
                    
                    self.activity_history.append(activity_snapshot)
                    
                    time.sleep(1.0)  # 1秒間隔
                    
                except Exception as e:
                    print(f"AI活動監視エラー: {e}")
                    time.sleep(1.0)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """監視を停止"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
    
    def get_current_ai_activity(self):
        """現在のAI活動状況を取得"""
        if not self.activity_history:
            return {
                'active': False,
                'process_count': 0,
                'processes': [],
                'directml_active': False
            }
        
        latest = self.activity_history[-1]
        return {
            'active': latest['ai_process_count'] > 0 or latest['directml_active'],
            'process_count': latest['ai_process_count'],
            'processes': latest['ai_processes'],
            'directml_active': latest['directml_active']
        }
    
    def get_ai_activity_summary(self, last_minutes=1):
        """指定時間内のAI活動サマリーを取得"""
        if not self.activity_history:
            return {'active_ratio': 0.0, 'peak_processes': 0}
        
        cutoff_time = time.time() - (last_minutes * 60)
        recent_activities = [
            activity for activity in self.activity_history 
            if activity['timestamp'] > cutoff_time
        ]
        
        if not recent_activities:
            return {'active_ratio': 0.0, 'peak_processes': 0}
        
        active_count = sum(1 for activity in recent_activities 
                          if activity['ai_process_count'] > 0 or activity['directml_active'])
        
        active_ratio = active_count / len(recent_activities)
        peak_processes = max(activity['ai_process_count'] for activity in recent_activities)
        
        return {
            'active_ratio': active_ratio,
            'peak_processes': peak_processes,
            'total_samples': len(recent_activities)
        }

class NPUUsageEstimator:
    """CPU使用率とAI活動の相関からNPU使用を推定"""
    
    def __init__(self):
        self.cpu_baseline = deque(maxlen=30)  # 30秒のベースライン
        self.cpu_during_ai = deque(maxlen=30)  # AI活動中のCPU使用率
        
    def update_baseline_cpu(self, cpu_percent):
        """AI非活動時のCPUベースラインを更新"""
        self.cpu_baseline.append(cpu_percent)
    
    def update_ai_cpu(self, cpu_percent):
        """AI活動中のCPU使用率を更新"""
        self.cpu_during_ai.append(cpu_percent)
    
    def estimate_npu_offload(self):
        """NPUオフロード推定値を計算"""
        if len(self.cpu_baseline) < 10 or len(self.cpu_during_ai) < 5:
            return None
        
        baseline_avg = sum(self.cpu_baseline) / len(self.cpu_baseline)
        ai_avg = sum(self.cpu_during_ai) / len(self.cpu_during_ai)
        
        # CPU使用率の差からNPUオフロードを推定
        if baseline_avg > 0:
            cpu_reduction_ratio = max(0, (baseline_avg - ai_avg) / baseline_avg)
            
            # NPU使用推定値（0-100%）
            # CPU負荷が20%以上減った場合、NPU使用の可能性が高い
            if cpu_reduction_ratio > 0.2:
                npu_estimate = min(100, cpu_reduction_ratio * 100)
            else:
                npu_estimate = 0
            
            return {
                'npu_usage_estimate': npu_estimate,
                'cpu_reduction_ratio': cpu_reduction_ratio,
                'baseline_cpu': baseline_avg,
                'ai_cpu': ai_avg
            }
        
        return None

def format_ai_activity_status(ai_detector, npu_estimator):
    """AI活動状況を整形して表示"""
    current_activity = ai_detector.get_current_ai_activity()
    activity_summary = ai_detector.get_ai_activity_summary()
    npu_estimate = npu_estimator.estimate_npu_offload()
    
    # AI活動状況
    if current_activity['active']:
        if current_activity['directml_active']:
            ai_status = f"DirectML active, {current_activity['process_count']} AI processes"
        else:
            ai_status = f"{current_activity['process_count']} AI processes"
    else:
        ai_status = "no AI activity"
    
    # NPU推定値
    if npu_estimate and npu_estimate['npu_usage_estimate'] > 0:
        npu_status = f"~{npu_estimate['npu_usage_estimate']:.0f}% (estimated)"
    else:
        npu_status = "n/a"
    
    return ai_status, npu_status

# 以下は既存のhardware_measure.pyに統合するためのコード例
if __name__ == "__main__":
    print("AI活動検出とNPU使用推定のテスト")
    print("=" * 50)
    
    # 検出器の初期化
    ai_detector = AIActivityDetector()
    npu_estimator = NPUUsageEstimator()
    
    # 監視開始
    ai_detector.start_monitoring()
    
    try:
        for i in range(30):  # 30秒間テスト
            time.sleep(1)
            
            # 現在のCPU使用率
            current_cpu = psutil.cpu_percent(interval=None)
            
            # AI活動確認
            current_activity = ai_detector.get_current_ai_activity()
            
            # NPU推定値更新
            if current_activity['active']:
                npu_estimator.update_ai_cpu(current_cpu)
            else:
                npu_estimator.update_baseline_cpu(current_cpu)
            
            # 状況表示
            ai_status, npu_status = format_ai_activity_status(ai_detector, npu_estimator)
            
            print(f"[{i+1:2d}s] CPU: {current_cpu:5.1f}% | AI: {ai_status} | NPU: {npu_status}")
            
            # 詳細情報（5秒おき）
            if (i + 1) % 5 == 0:
                activity_summary = ai_detector.get_ai_activity_summary()
                print(f"     AI活動率: {activity_summary['active_ratio']*100:.1f}% (最大{activity_summary['peak_processes']}プロセス)")
                
                if current_activity['processes']:
                    print(f"     検出プロセス: {[p[1] for p in current_activity['processes'][:3]]}")
    
    except KeyboardInterrupt:
        print("\n監視停止")
    
    finally:
        ai_detector.stop_monitoring()
    
    print("\nテスト完了")