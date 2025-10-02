#!/usr/bin/env python3
"""
Intel NPU ETW監視テストスクリプト
発見されたIntel NPU ETWプロバイダーを実際に使用してテスト
"""

import subprocess
import time
import os
import json
from datetime import datetime
from typing import Dict, List, Optional

class IntelNPUETWMonitor:
    """Intel NPU ETW監視クラス"""
    
    def __init__(self):
        self.npu_providers = {
            "Intel-NPU-D3D12": "{11A83531-4AC9-4142-8D35-E474B6B3C597}",
            "Intel-NPU-Kmd": "{B3B1AAB1-3C04-4B6D-A069-59547BC18233}",
            "Intel-NPU-LevelZero": "{416F823F-2CE2-44B9-A1BA-7E98BA4CD4BA}"
        }
        
        self.active_sessions = []
        self.trace_files = []
    
    def test_provider_availability(self) -> Dict[str, bool]:
        """NPUプロバイダーの利用可能性をテスト"""
        print("Testing Intel NPU ETW provider availability...")
        
        results = {}
        
        for provider_name, provider_guid in self.npu_providers.items():
            print(f"\nTesting {provider_name}...")
            
            try:
                # 短時間のテストセッションを開始
                session_name = f"NPU_Test_{provider_name.replace('-', '_')}"
                trace_file = f"test_{provider_name.lower().replace('-', '_')}.etl"
                
                # ETWセッション開始
                start_cmd = [
                    "logman", "start", session_name,
                    "-p", provider_guid,
                    "-o", trace_file,
                    "-ets"
                ]
                
                result = subprocess.run(start_cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    print(f"  ✓ Successfully started ETW session")
                    
                    # 短時間待機
                    time.sleep(2)
                    
                    # セッション停止
                    stop_cmd = ["logman", "stop", session_name, "-ets"]
                    stop_result = subprocess.run(stop_cmd, capture_output=True, text=True, timeout=10)
                    
                    if stop_result.returncode == 0:
                        print(f"  ✓ Successfully stopped ETW session")
                        
                        # ファイルサイズ確認
                        if os.path.exists(trace_file):
                            file_size = os.path.getsize(trace_file)
                            print(f"  ✓ Trace file created: {file_size} bytes")
                            
                            if file_size > 1024:  # 1KB以上なら有効なデータがある可能性
                                results[provider_name] = True
                                print(f"  🎯 Provider appears to be ACTIVE and generating events!")
                            else:
                                results[provider_name] = False
                                print(f"  ⚠ Provider available but no significant events generated")
                            
                            # テストファイルを削除
                            try:
                                os.remove(trace_file)
                            except:
                                pass
                        else:
                            results[provider_name] = False
                            print(f"  ⚠ No trace file generated")
                    else:
                        results[provider_name] = False
                        print(f"  ✗ Failed to stop session: {stop_result.stderr}")
                else:
                    results[provider_name] = False
                    print(f"  ✗ Failed to start session: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                results[provider_name] = False
                print(f"  ✗ Timeout during ETW session test")
                
                # クリーンアップ
                try:
                    subprocess.run(["logman", "stop", session_name, "-ets"], 
                                 capture_output=True, timeout=5)
                except:
                    pass
                    
            except Exception as e:
                results[provider_name] = False
                print(f"  ✗ Error testing provider: {e}")
        
        return results
    
    def start_comprehensive_npu_monitoring(self, duration: int = 30) -> bool:
        """包括的NPU監視を開始"""
        print(f"\nStarting comprehensive Intel NPU ETW monitoring for {duration} seconds...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        active_providers = []
        
        # 各プロバイダーで個別セッションを開始
        for provider_name, provider_guid in self.npu_providers.items():
            session_name = f"NPU_{provider_name.replace('-', '_')}_{timestamp}"
            trace_file = f"npu_{provider_name.lower().replace('-', '_')}_{timestamp}.etl"
            
            try:
                start_cmd = [
                    "logman", "start", session_name,
                    "-p", provider_guid,
                    "-o", trace_file,
                    "-ets",
                    "-nb", "128", "256"  # Buffer settings for better capture
                ]
                
                result = subprocess.run(start_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"  ✓ Started monitoring {provider_name}")
                    active_providers.append({
                        'name': provider_name,
                        'session': session_name,
                        'file': trace_file,
                        'guid': provider_guid
                    })
                    self.active_sessions.append(session_name)
                    self.trace_files.append(trace_file)
                else:
                    print(f"  ✗ Failed to start {provider_name}: {result.stderr}")
                    
            except Exception as e:
                print(f"  ✗ Error starting {provider_name}: {e}")
        
        if not active_providers:
            print("❌ No NPU providers could be started")
            return False
        
        print(f"\n🚀 Monitoring {len(active_providers)} NPU providers...")
        print("💡 Now would be a good time to run AI applications to generate NPU events!")
        print("   Try running: AI inference, image processing, or machine learning tasks")
        
        # 指定時間待機
        for i in range(duration):
            remaining = duration - i
            print(f"\r⏱ Monitoring... {remaining:02d}s remaining", end='', flush=True)
            time.sleep(1)
        
        print(f"\n⏹ Stopping NPU monitoring...")
        
        # すべてのセッションを停止
        stopped_successfully = 0
        for provider in active_providers:
            try:
                stop_cmd = ["logman", "stop", provider['session'], "-ets"]
                result = subprocess.run(stop_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"  ✓ Stopped {provider['name']}")
                    stopped_successfully += 1
                else:
                    print(f"  ✗ Error stopping {provider['name']}: {result.stderr}")
                    
            except Exception as e:
                print(f"  ✗ Exception stopping {provider['name']}: {e}")
        
        print(f"\n✅ Monitoring completed! Stopped {stopped_successfully}/{len(active_providers)} sessions")
        return stopped_successfully > 0
    
    def analyze_collected_traces(self) -> Dict[str, any]:
        """収集されたトレースファイルを分析"""
        print(f"\n📊 Analyzing collected NPU trace files...")
        
        analysis_results = {
            'total_files': len(self.trace_files),
            'file_analysis': [],
            'summary': {},
            'recommendations': []
        }
        
        total_size = 0
        active_files = 0
        
        for trace_file in self.trace_files:
            file_info = {
                'file': trace_file,
                'exists': False,
                'size_bytes': 0,
                'size_mb': 0.0,
                'has_events': False
            }
            
            if os.path.exists(trace_file):
                file_info['exists'] = True
                file_size = os.path.getsize(trace_file)
                file_info['size_bytes'] = file_size
                file_info['size_mb'] = file_size / (1024 * 1024)
                total_size += file_size
                
                # 有意なイベントがあるかチェック（1KB以上）
                if file_size > 1024:
                    file_info['has_events'] = True
                    active_files += 1
                    print(f"  📄 {trace_file}: {file_info['size_mb']:.2f} MB ✅ Has events")
                else:
                    print(f"  📄 {trace_file}: {file_info['size_mb']:.2f} MB ⚠ Minimal data")
            else:
                print(f"  📄 {trace_file}: ❌ File not found")
            
            analysis_results['file_analysis'].append(file_info)
        
        # サマリー作成
        analysis_results['summary'] = {
            'total_trace_files': len(self.trace_files),
            'files_with_events': active_files,
            'total_size_mb': total_size / (1024 * 1024),
            'avg_file_size_mb': (total_size / len(self.trace_files) / (1024 * 1024)) if self.trace_files else 0
        }
        
        # 推奨事項生成
        if active_files > 0:
            analysis_results['recommendations'].extend([
                f"✅ {active_files} NPU trace files contain events!",
                "🔍 Recommended next steps:",
                "1. Use Windows Performance Analyzer (WPA) for detailed analysis:",
                f"   wpa.exe {self.trace_files[0] if self.trace_files else 'trace_file.etl'}",
                "2. Convert ETL to text for manual analysis:",
                f"   wevtutil qe {self.trace_files[0] if self.trace_files else 'trace_file.etl'} /lf:true /f:text > npu_events.txt",
                "3. Look for NPU utilization patterns during AI workload execution",
                "4. Correlate ETW events with application-level AI activity"
            ])
        else:
            analysis_results['recommendations'].extend([
                "⚠ No significant NPU events captured in traces",
                "💡 Possible reasons:",
                "1. NPU was not active during monitoring period",
                "2. AI applications did not use NPU acceleration",
                "3. NPU drivers may not generate ETW events in current version",
                "🔄 Recommended retry steps:",
                "1. Run AI inference applications during monitoring",
                "2. Try longer monitoring duration (60+ seconds)",
                "3. Ensure AI applications are configured to use NPU acceleration"
            ])
        
        return analysis_results
    
    def cleanup_monitoring(self):
        """監視セッションのクリーンアップ"""
        print(f"\n🧹 Cleaning up monitoring sessions...")
        
        # アクティブセッションを強制停止
        for session in self.active_sessions:
            try:
                subprocess.run(["logman", "stop", session, "-ets"], 
                             capture_output=True, timeout=5)
            except:
                pass
        
        print("✅ Cleanup completed")
    
    def comprehensive_npu_etw_test(self, monitor_duration: int = 30):
        """包括的NPU ETW テスト"""
        print("=" * 80)
        print(" INTEL NPU ETW MONITORING TEST")
        print(" Testing discovered Intel NPU ETW providers")
        print("=" * 80)
        
        try:
            # 1. プロバイダー利用可能性テスト
            availability_results = self.test_provider_availability()
            
            print(f"\n📋 Provider Availability Results:")
            available_count = 0
            for provider, available in availability_results.items():
                status = "✅ Available & Active" if available else "⚠ Available but Inactive"
                print(f"  {provider}: {status}")
                if available:
                    available_count += 1
            
            if available_count == 0:
                print("\n❌ No NPU providers are generating events")
                print("💡 This may indicate NPU is not currently active")
                return
            
            print(f"\n🎯 Found {available_count} active NPU providers!")
            
            # 2. 包括的監視実行
            success = self.start_comprehensive_npu_monitoring(monitor_duration)
            
            if not success:
                print("❌ Failed to start comprehensive monitoring")
                return
            
            # 3. トレース分析
            analysis = self.analyze_collected_traces()
            
            # 4. 結果表示
            print(f"\n{'='*60}")
            print(" FINAL RESULTS")
            print(f"{'='*60}")
            
            summary = analysis['summary']
            print(f"📊 Monitoring Summary:")
            print(f"  Total trace files: {summary['total_trace_files']}")
            print(f"  Files with events: {summary['files_with_events']}")
            print(f"  Total data collected: {summary['total_size_mb']:.2f} MB")
            print(f"  Average file size: {summary['avg_file_size_mb']:.2f} MB")
            
            print(f"\n💡 Recommendations:")
            for recommendation in analysis['recommendations']:
                print(f"  {recommendation}")
                
        except KeyboardInterrupt:
            print(f"\n\n⚠ Monitoring interrupted by user")
        except Exception as e:
            print(f"\n❌ Error during NPU ETW testing: {e}")
        finally:
            # 必ずクリーンアップ
            self.cleanup_monitoring()

def main():
    """メイン関数"""
    print("Intel NPU ETW Monitoring Test")
    print("Testing discovered Intel NPU ETW providers for real-time monitoring")
    print()
    
    monitor = IntelNPUETWMonitor()
    
    # 短時間のテスト実行
    test_duration = 20  # 20秒のテスト
    print(f"⏱ Test duration: {test_duration} seconds")
    print("💡 For best results, run AI applications during monitoring")
    print()
    
    monitor.comprehensive_npu_etw_test(test_duration)

if __name__ == "__main__":
    main()