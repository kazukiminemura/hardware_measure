#!/usr/bin/env python3
"""
GPU Compute Engine NPU関連性調査
ComputeエンジンがNPUと関連しているか詳細調査
"""

import time
import statistics
from typing import List, Dict, Tuple
from collections import defaultdict, deque

try:
    import win32pdh
    HAS_PDH = True
except ImportError:
    HAS_PDH = False

class ComputeEngineNPUAnalyzer:
    """GPU ComputeエンジンのNPU関連性分析"""
    
    def __init__(self):
        self.compute_counters = []
        self.all_gpu_counters = []
        self.monitoring_data = defaultdict(deque)
        
    def discover_compute_engines(self) -> List[str]:
        """ComputeエンジンカウンターをすべてDiscover"""
        print("Discovering GPU Compute engines...")
        
        try:
            # すべてのGPU Engineカウンターを取得
            all_gpu_paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*)\Utilization Percentage")
            
            compute_engines = []
            engine_breakdown = defaultdict(int)
            
            for path in all_gpu_paths:
                # エンジンタイプを特定
                if 'engtype_' in path:
                    engtype_start = path.find('engtype_') + 8
                    engtype_end = path.find(')', engtype_start)
                    if engtype_end > engtype_start:
                        engtype = path[engtype_start:engtype_end]
                        engine_breakdown[engtype] += 1
                        
                        # Computeエンジンのみを保存
                        if engtype == 'Compute':
                            compute_engines.append(path)
            
            print(f"GPU Engine breakdown:")
            for engtype, count in engine_breakdown.items():
                print(f"  {engtype}: {count} engines")
            
            print(f"\nCompute engines found: {len(compute_engines)}")
            
            # Computeエンジンの詳細を表示
            if compute_engines:
                print(f"First 3 Compute engines:")
                for i, engine in enumerate(compute_engines[:3]):
                    print(f"  {i+1}. {engine}")
            
            self.compute_counters = compute_engines
            self.all_gpu_counters = all_gpu_paths
            
            return compute_engines
            
        except Exception as e:
            print(f"Error discovering compute engines: {e}")
            return []
    
    def sample_compute_engine_activity(self, duration: int = 30) -> Dict[str, any]:
        """Computeエンジンの活動をサンプリング"""
        print(f"\nSampling Compute engine activity for {duration} seconds...")
        
        if not self.compute_counters:
            print("No compute counters available")
            return {}
        
        # 最初の数個のComputeエンジンをモニター（パフォーマンス考慮）
        monitor_engines = self.compute_counters[:5]  # 最初の5個
        print(f"Monitoring {len(monitor_engines)} compute engines...")
        
        try:
            # クエリとカウンターのセットアップ
            query = win32pdh.OpenQuery()
            counters = {}
            
            for i, path in enumerate(monitor_engines):
                try:
                    counter = win32pdh.AddCounter(query, path)
                    counters[f"compute_{i}"] = {
                        'counter': counter,
                        'path': path,
                        'values': []
                    }
                except Exception as e:
                    print(f"  Warning: Could not add counter {i}: {e}")
            
            if not counters:
                print("No counters successfully added")
                return {}
            
            print(f"Successfully added {len(counters)} counters")
            
            # サンプリング開始
            sample_interval = 1.0  # 1秒間隔
            samples = int(duration / sample_interval)
            
            # 初回データ収集
            win32pdh.CollectQueryData(query)
            time.sleep(sample_interval)
            
            print(f"Collecting samples... (0/{samples})", end='', flush=True)
            
            for sample in range(samples):
                win32pdh.CollectQueryData(query)
                
                # 各カウンターの値を取得
                for counter_name, counter_info in counters.items():
                    try:
                        _, value = win32pdh.GetFormattedCounterValue(
                            counter_info['counter'], 
                            win32pdh.PDH_FMT_DOUBLE
                        )
                        counter_info['values'].append(value)
                    except Exception as e:
                        # エラーの場合は0を記録
                        counter_info['values'].append(0.0)
                
                # プログレス表示
                if (sample + 1) % 5 == 0:
                    print(f"\rCollecting samples... ({sample + 1}/{samples})", end='', flush=True)
                
                if sample < samples - 1:  # 最後のサンプル以外
                    time.sleep(sample_interval)
            
            print(f"\rSampling completed! ({samples}/{samples})")
            
            # データ分析
            analysis_results = {}
            
            for counter_name, counter_info in counters.items():
                values = counter_info['values']
                if values:
                    analysis_results[counter_name] = {
                        'path': counter_info['path'],
                        'total_samples': len(values),
                        'avg_utilization': statistics.mean(values),
                        'max_utilization': max(values),
                        'min_utilization': min(values),
                        'std_dev': statistics.stdev(values) if len(values) > 1 else 0.0,
                        'active_samples': sum(1 for v in values if v > 1.0),  # 1%以上を活動中とみなす
                        'values': values[-10:]  # 最後の10サンプル
                    }
            
            win32pdh.CloseQuery(query)
            return analysis_results
            
        except Exception as e:
            print(f"Error during sampling: {e}")
            return {}
    
    def analyze_npu_correlation(self, analysis_data: Dict[str, any]) -> Dict[str, any]:
        """NPUとの関連性を分析"""
        print(f"\nAnalyzing NPU correlation patterns...")
        
        if not analysis_data:
            print("No analysis data available")
            return {}
        
        correlation_results = {
            'highly_active_engines': [],
            'moderately_active_engines': [],
            'inactive_engines': [],
            'potential_npu_engines': [],
            'summary': {}
        }
        
        total_engines = len(analysis_data)
        total_active = 0
        high_activity_threshold = 5.0  # 5%以上の平均使用率
        moderate_activity_threshold = 1.0  # 1%以上の平均使用率
        
        print(f"Analyzing {total_engines} compute engines...")
        
        for counter_name, data in analysis_data.items():
            avg_util = data['avg_utilization']
            max_util = data['max_utilization']
            active_samples = data['active_samples']
            total_samples = data['total_samples']
            activity_ratio = active_samples / total_samples if total_samples > 0 else 0
            
            print(f"\n{counter_name}:")
            print(f"  Path: {data['path'][:60]}...")
            print(f"  Avg utilization: {avg_util:.2f}%")
            print(f"  Max utilization: {max_util:.2f}%")
            print(f"  Active samples: {active_samples}/{total_samples} ({activity_ratio*100:.1f}%)")
            print(f"  Std deviation: {data['std_dev']:.2f}")
            
            # 分類
            if avg_util >= high_activity_threshold:
                correlation_results['highly_active_engines'].append({
                    'name': counter_name,
                    'path': data['path'],
                    'avg_utilization': avg_util,
                    'activity_ratio': activity_ratio
                })
                total_active += 1
                print(f"  → HIGH ACTIVITY (potential NPU candidate)")
                
            elif avg_util >= moderate_activity_threshold:
                correlation_results['moderately_active_engines'].append({
                    'name': counter_name,
                    'path': data['path'],
                    'avg_utilization': avg_util,
                    'activity_ratio': activity_ratio
                })
                total_active += 1
                print(f"  → Moderate activity")
                
            else:
                correlation_results['inactive_engines'].append({
                    'name': counter_name,
                    'path': data['path'],
                    'avg_utilization': avg_util
                })
                print(f"  → Inactive")
            
            # NPU候補の特定（高活動度またはパターン的特徴）
            npu_score = 0
            if avg_util > 2.0:  # 2%以上の平均使用率
                npu_score += 30
            if max_util > 10.0:  # 10%以上のピーク使用率
                npu_score += 25
            if activity_ratio > 0.3:  # 30%以上のサンプルで活動
                npu_score += 25
            if data['std_dev'] > 5.0:  # 変動が大きい（バースト的使用）
                npu_score += 20
            
            if npu_score >= 50:  # 50点以上をNPU候補とする
                correlation_results['potential_npu_engines'].append({
                    'name': counter_name,
                    'path': data['path'],
                    'npu_score': npu_score,
                    'avg_utilization': avg_util,
                    'characteristics': []
                })
                print(f"  → NPU CANDIDATE (score: {npu_score})")
        
        # サマリー
        correlation_results['summary'] = {
            'total_engines_analyzed': total_engines,
            'active_engines': total_active,
            'activity_rate': total_active / total_engines if total_engines > 0 else 0,
            'high_activity_engines': len(correlation_results['highly_active_engines']),
            'potential_npu_engines': len(correlation_results['potential_npu_engines'])
        }
        
        return correlation_results
    
    def generate_npu_monitoring_recommendation(self, correlation_data: Dict[str, any]) -> str:
        """NPUモニタリング推奨事項を生成"""
        print(f"\n{'='*60}")
        print(" NPU MONITORING RECOMMENDATIONS")
        print(f"{'='*60}")
        
        if not correlation_data:
            return "No correlation data available for recommendations"
        
        summary = correlation_data.get('summary', {})
        potential_npu = correlation_data.get('potential_npu_engines', [])
        highly_active = correlation_data.get('highly_active_engines', [])
        
        recommendations = []
        
        print(f"Analysis Summary:")
        print(f"  Total Compute engines: {summary.get('total_engines_analyzed', 0)}")
        print(f"  Active engines: {summary.get('active_engines', 0)}")
        print(f"  High activity engines: {summary.get('high_activity_engines', 0)}")
        print(f"  Potential NPU engines: {summary.get('potential_npu_engines', 0)}")
        
        if potential_npu:
            print(f"\nTOP NPU CANDIDATES:")
            for i, engine in enumerate(sorted(potential_npu, key=lambda x: x['npu_score'], reverse=True)):
                print(f"  {i+1}. Score: {engine['npu_score']}, Avg: {engine['avg_utilization']:.2f}%")
                print(f"     Path: {engine['path']}")
                recommendations.append(engine['path'])
        
        elif highly_active:
            print(f"\nFALLBACK CANDIDATES (high activity):")
            for i, engine in enumerate(highly_active):
                print(f"  {i+1}. Avg: {engine['avg_utilization']:.2f}%")
                print(f"     Path: {engine['path']}")
                recommendations.append(engine['path'])
        
        else:
            print(f"\nNo significant compute engine activity detected.")
            print(f"This suggests either:")
            print(f"  1. NPU is not currently active")
            print(f"  2. NPU activity is not reflected in GPU Compute engines")
            print(f"  3. NPU has separate, undiscovered performance counters")
        
        # 実装推奨事項
        print(f"\nIMPLEMENTATION RECOMMENDATIONS:")
        if recommendations:
            print(f"1. Monitor these specific compute engine counters:")
            for path in recommendations[:3]:  # 上位3つ
                print(f"   - {path}")
            print(f"2. Set up alerting for utilization > 5%")
            print(f"3. Correlate with AI application launches")
            print(f"4. Monitor patterns during known AI workloads")
        else:
            print(f"1. Use indirect monitoring methods (CPU patterns, power, process detection)")
            print(f"2. Monitor for AI framework process launches")
            print(f"3. Consider using DirectML/WinML API hooks")
            print(f"4. Wait for Windows 11 24H2+ NPU counter support")
        
        return "\n".join(recommendations) if recommendations else "Use indirect monitoring"
    
    def comprehensive_compute_npu_analysis(self, sampling_duration: int = 30):
        """包括的なCompute-NPU分析"""
        print("=" * 80)
        print(" GPU COMPUTE ENGINE NPU CORRELATION ANALYSIS")
        print("=" * 80)
        
        if not HAS_PDH:
            print("ERROR: win32pdh not available")
            return
        
        # 1. Computeエンジンの発見
        compute_engines = self.discover_compute_engines()
        
        if not compute_engines:
            print("No Compute engines found. Cannot perform NPU correlation analysis.")
            return
        
        # 2. 活動サンプリング
        analysis_data = self.sample_compute_engine_activity(sampling_duration)
        
        if not analysis_data:
            print("No sampling data collected. Cannot perform correlation analysis.")
            return
        
        # 3. NPU関連性分析
        correlation_results = self.analyze_npu_correlation(analysis_data)
        
        # 4. 推奨事項生成
        recommendations = self.generate_npu_monitoring_recommendation(correlation_results)
        
        return {
            'compute_engines': compute_engines,
            'analysis_data': analysis_data,
            'correlation_results': correlation_results,
            'recommendations': recommendations
        }

def main():
    """メイン関数"""
    print("GPU Compute Engine NPU Correlation Analysis")
    print("Investigating if GPU Compute engines correlate with NPU activity")
    print()
    
    analyzer = ComputeEngineNPUAnalyzer()
    
    # 短時間のサンプリング（デモ用）
    sampling_duration = 15  # 15秒
    print(f"Note: Using {sampling_duration} second sampling for demonstration")
    print("For production monitoring, consider longer duration (60+ seconds)")
    print()
    
    results = analyzer.comprehensive_compute_npu_analysis(sampling_duration)
    
    if results:
        print(f"\nAnalysis completed successfully!")
        print(f"Use the recommended monitoring approach for NPU detection.")

if __name__ == "__main__":
    main()