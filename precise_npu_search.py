#!/usr/bin/env python3
"""
win32pdh 精密NPU/AI検索スクリプト
より精密にNPU/AI関連オブジェクトを特定
"""

import time
from typing import List, Dict, Set
from collections import defaultdict

try:
    import win32pdh
    HAS_PDH = True
except ImportError:
    HAS_PDH = False

class PreciseNPUSearcher:
    """精密NPU/AI オブジェクト検索クラス"""
    
    def __init__(self):
        self.npu_specific_patterns = [
            # NPU専用パターン
            r"\NPU Engine(*)\*",
            r"\NPU Engine(*)\Utilization Percentage",
            r"\NPU Process Memory(*)\*",
            r"\NPU Adapter Memory(*)\*",
            
            # Intel AI Boost専用
            r"\Intel AI Boost(*)\*",
            r"\Intel(R) AI Boost(*)\*",
            r"\AI Boost(*)\*",
            
            # Neural Processing Unit
            r"\Neural Processing Unit(*)\*",
            r"\Neural Engine(*)\*",
            r"\AI Processing Unit(*)\*",
            r"\AI Accelerator(*)\*",
        ]
        
        self.related_patterns = [
            # GPU Engineの中でAI/Compute関連
            r"\GPU Engine(*engtype_Compute)\*",
            r"\GPU Engine(*AI*)\*",
            r"\GPU Engine(*Neural*)\*",
            r"\GPU Engine(*NPU*)\*",
            
            # Processor Informationの中で特殊なもの
            r"\Processor Information(*AI*)\*",
            r"\Processor Information(*Neural*)\*",
            r"\Processor Information(*NPU*)\*",
        ]
    
    def search_exact_npu_objects(self) -> Dict[str, List[str]]:
        """正確なNPUオブジェクト検索"""
        print("Searching for exact NPU/AI performance objects...")
        
        results = {}
        
        for pattern in self.npu_specific_patterns:
            print(f"\nTesting pattern: {pattern}")
            try:
                paths = win32pdh.ExpandCounterPath(pattern)
                if paths:
                    print(f"  ✓ Found {len(paths)} counters!")
                    results[pattern] = list(paths)
                    
                    # 最初の3つを表示
                    for i, path in enumerate(paths[:3]):
                        print(f"    {i+1}. {path}")
                    if len(paths) > 3:
                        print(f"    ... and {len(paths) - 3} more")
                else:
                    print("  ✗ No counters found")
            except Exception as e:
                print(f"  ✗ Error: {e}")
        
        return results
    
    def analyze_gpu_engines_for_npu(self) -> Dict[str, any]:
        """GPU Engineの中からNPU関連を分析"""
        print(f"\nAnalyzing GPU Engines for NPU/AI patterns...")
        
        try:
            # すべてのGPU Engineカウンターを取得
            all_gpu_paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*)\Utilization Percentage")
            
            if not all_gpu_paths:
                print("  No GPU Engine counters found")
                return {}
            
            print(f"  Total GPU Engine instances: {len(all_gpu_paths)}")
            
            # エンジンタイプ別に分類
            engine_types = defaultdict(list)
            npu_candidates = []
            
            for path in all_gpu_paths:
                # エンジンタイプを抽出
                if 'engtype_' in path:
                    engtype_start = path.find('engtype_') + 8
                    engtype_end = path.find(')', engtype_start)
                    if engtype_end > engtype_start:
                        engtype = path[engtype_start:engtype_end]
                        engine_types[engtype].append(path)
                    
                    # NPU/AI関連キーワードチェック
                    path_lower = path.lower()
                    if any(kw in path_lower for kw in ['npu', 'ai', 'neural', 'boost', 'ml']):
                        npu_candidates.append(path)
                else:
                    # エンジンタイプが明示されていない場合
                    engine_types['Unknown'].append(path)
            
            print(f"\nEngine Types found:")
            for engtype, paths in engine_types.items():
                print(f"  {engtype}: {len(paths)} engines")
                
                # 各タイプの代表例を表示
                if paths:
                    example = paths[0]
                    print(f"    Example: {example[:80]}{'...' if len(example) > 80 else ''}")
            
            if npu_candidates:
                print(f"\nPotential NPU/AI GPU Engines: {len(npu_candidates)}")
                for candidate in npu_candidates[:3]:
                    print(f"  - {candidate}")
            
            return {
                'total_engines': len(all_gpu_paths),
                'engine_types': dict(engine_types),
                'npu_candidates': npu_candidates
            }
            
        except Exception as e:
            print(f"  Error analyzing GPU engines: {e}")
            return {}
    
    def check_processor_information_details(self) -> Dict[str, any]:
        """Processor Informationの詳細分析"""
        print(f"\nAnalyzing Processor Information for NPU details...")
        
        try:
            # Processor Informationのすべてのカウンターを取得
            proc_counters = win32pdh.EnumObjectItems(None, None, "Processor Information", 0)
            
            if not proc_counters:
                print("  No Processor Information counters found")
                return {}
            
            counters = proc_counters[0] if proc_counters else []
            instances = proc_counters[1] if len(proc_counters) > 1 else []
            
            print(f"  Processor counters: {len(counters)}")
            print(f"  Processor instances: {len(instances)}")
            
            # NPU/AI関連のカウンターを検索
            npu_related_counters = []
            for counter in counters:
                counter_lower = counter.lower()
                if any(kw in counter_lower for kw in ['npu', 'ai', 'neural', 'boost', 'accelerator']):
                    npu_related_counters.append(counter)
            
            if npu_related_counters:
                print(f"\nPotential NPU-related processor counters:")
                for counter in npu_related_counters:
                    print(f"  - {counter}")
            else:
                print(f"\nNo obvious NPU-related processor counters found")
                print(f"Available counters (first 10):")
                for counter in counters[:10]:
                    print(f"  - {counter}")
                if len(counters) > 10:
                    print(f"  ... and {len(counters) - 10} more")
            
            # インスタンスの詳細分析
            print(f"\nProcessor instances:")
            for instance in instances:
                print(f"  - {instance}")
            
            return {
                'total_counters': len(counters),
                'total_instances': len(instances),
                'npu_related_counters': npu_related_counters,
                'all_counters': counters,
                'instances': instances
            }
            
        except Exception as e:
            print(f"  Error analyzing processor information: {e}")
            return {}
    
    def test_potential_npu_paths(self) -> List[str]:
        """潜在的なNPUパスをテスト"""
        print(f"\nTesting potential NPU counter paths...")
        
        test_paths = [
            # 直接的なNPUパス
            r"\NPU Engine(_Total)\Utilization Percentage",
            r"\NPU\Utilization Percentage",
            r"\Intel AI Boost\Utilization Percentage",
            r"\Neural Processing Unit\Utilization Percentage",
            r"\AI Accelerator\Utilization Percentage",
            
            # プロセッサー情報内のNPU関連
            r"\Processor Information(_Total)\NPU Utilization",
            r"\Processor Information(_Total)\AI Utilization",
            r"\Processor Information(_Total)\Neural Usage",
            
            # GPU Engine内のCompute（NPUの可能性）
            r"\GPU Engine(_Total)\Utilization Percentage",
        ]
        
        working_paths = []
        
        for path in test_paths:
            print(f"  Testing: {path}")
            if self._test_counter_path(path):
                print(f"    ✓ Working!")
                working_paths.append(path)
            else:
                print(f"    ✗ Not available")
        
        return working_paths
    
    def _test_counter_path(self, path: str) -> bool:
        """カウンターパスのテスト"""
        try:
            query = win32pdh.OpenQuery()
            counter = win32pdh.AddCounter(query, path)
            
            win32pdh.CollectQueryData(query)
            time.sleep(0.1)
            win32pdh.CollectQueryData(query)
            
            t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
            
            win32pdh.CloseQuery(query)
            return True
        except:
            return False
    
    def investigate_power_and_thermal(self) -> Dict[str, any]:
        """電力・温度関連の調査（NPU使用の間接指標）"""
        print(f"\nInvestigating Power and Thermal counters...")
        
        results = {}
        
        # 電力関連
        try:
            power_paths = win32pdh.ExpandCounterPath(r"\Power Meter(*)\*")
            if power_paths:
                print(f"  Power Meter counters: {len(power_paths)}")
                results['power_paths'] = power_paths[:5]  # 最初の5個
                for path in power_paths[:3]:
                    print(f"    {path}")
            else:
                print(f"  No Power Meter counters found")
        except:
            print(f"  Error accessing Power Meter counters")
        
        # 温度関連
        try:
            thermal_paths = win32pdh.ExpandCounterPath(r"\Thermal Zone Information(*)\*")
            if thermal_paths:
                print(f"  Thermal Zone counters: {len(thermal_paths)}")
                results['thermal_paths'] = thermal_paths[:5]  # 最初の5個
                for path in thermal_paths[:3]:
                    print(f"    {path}")
            else:
                print(f"  No Thermal Zone counters found")
        except:
            print(f"  Error accessing Thermal Zone counters")
        
        return results
    
    def comprehensive_npu_investigation(self):
        """包括的NPU調査"""
        print("=" * 80)
        print(" Precise NPU/AI Performance Objects Investigation")
        print("=" * 80)
        
        if not HAS_PDH:
            print("ERROR: win32pdh not available")
            return
        
        # 1. 正確なNPUオブジェクト検索
        npu_objects = self.search_exact_npu_objects()
        
        # 2. GPU Engine分析
        gpu_analysis = self.analyze_gpu_engines_for_npu()
        
        # 3. Processor Information分析
        proc_analysis = self.check_processor_information_details()
        
        # 4. 潜在的パステスト
        working_paths = self.test_potential_npu_paths()
        
        # 5. 電力・温度調査
        power_thermal = self.investigate_power_and_thermal()
        
        # 結論
        print(f"\n{'='*80}")
        print(" PRECISE INVESTIGATION RESULTS")
        print(f"{'='*80}")
        
        print(f"Direct NPU Objects Found: {len(npu_objects)}")
        if npu_objects:
            print("  ✓ Direct NPU performance counters are available!")
            for pattern, paths in npu_objects.items():
                print(f"    Pattern: {pattern}")
                print(f"    Counters: {len(paths)}")
        else:
            print("  ✗ No direct NPU performance counters found")
        
        if gpu_analysis:
            total_engines = gpu_analysis.get('total_engines', 0)
            npu_candidates = gpu_analysis.get('npu_candidates', [])
            print(f"\nGPU Engine Analysis:")
            print(f"  Total GPU engines: {total_engines}")
            print(f"  NPU candidates: {len(npu_candidates)}")
        
        if proc_analysis:
            npu_counters = proc_analysis.get('npu_related_counters', [])
            print(f"\nProcessor Information Analysis:")
            print(f"  NPU-related counters: {len(npu_counters)}")
        
        print(f"\nWorking test paths: {len(working_paths)}")
        for path in working_paths:
            print(f"  ✓ {path}")
        
        # 推奨事項
        if not npu_objects and not working_paths:
            print(f"\n{'='*60}")
            print(" RECOMMENDATION")
            print(f"{'='*60}")
            print("No direct NPU performance counters found.")
            print("This is expected for current Windows versions.")
            print("\nRecommended monitoring approach:")
            print("1. Use GPU Engine monitoring for GPU-integrated NPU")
            print("2. Monitor AI process CPU usage patterns")
            print("3. Track power consumption changes during AI tasks")
            print("4. Use DirectML/WinML API-level monitoring")

def main():
    """メイン関数"""
    print("Precise NPU/AI Object Search using win32pdh")
    print("Focused search for exact NPU performance objects")
    print()
    
    searcher = PreciseNPUSearcher()
    searcher.comprehensive_npu_investigation()

if __name__ == "__main__":
    main()