#!/usr/bin/env python3
"""
win32pdh NPU/AI オブジェクト詳細検索スクリプト
Performance Data Helper APIを使用してNPU/AI関連のオブジェクトを包括的に検索
"""

import re
import time
import subprocess
from typing import List, Dict, Set, Tuple
from collections import defaultdict

try:
    import win32pdh
    import win32api
    HAS_PDH = True
except ImportError:
    HAS_PDH = False

class PDHObjectSearcher:
    """PDH Performance Object 検索クラス"""
    
    def __init__(self):
        self.search_keywords = [
            # NPU関連キーワード
            'npu', 'neural', 'ai', 'boost', 'accelerator', 'inference',
            
            # Intel AI Boost関連
            'intel', 'ai boost', 'neural processing', 'machine learning',
            
            # 処理関連
            'compute', 'engine', 'processor', 'unit',
            
            # その他AI関連
            'directml', 'winml', 'onnx', 'tensor', 'deep learning'
        ]
        
        self.object_categories = {
            'Engine': [],
            'Processor': [],
            'Memory': [],
            'Power': [],
            'GPU': [],
            'System': [],
            'Process': [],
            'Other': []
        }
    
    def enumerate_all_performance_objects(self) -> List[str]:
        """すべてのパフォーマンスオブジェクトを列挙"""
        print("Enumerating all Performance Objects...")
        
        if not HAS_PDH:
            print("ERROR: win32pdh not available")
            return []
        
        try:
            # EnumObjectsでオブジェクト一覧を取得
            objects = win32pdh.EnumObjects(None, None, 0)
            print(f"Found {len(objects)} performance objects")
            return sorted(objects)
        except Exception as e:
            print(f"Error enumerating objects: {e}")
            return []
    
    def search_objects_by_keywords(self, objects: List[str]) -> Dict[str, List[str]]:
        """キーワードによるオブジェクト検索"""
        print(f"\nSearching {len(objects)} objects for NPU/AI keywords...")
        
        matches = defaultdict(list)
        
        for obj in objects:
            obj_lower = obj.lower()
            
            for keyword in self.search_keywords:
                if keyword.lower() in obj_lower:
                    matches[keyword].append(obj)
                    break
        
        return dict(matches)
    
    def get_object_counters(self, object_name: str) -> List[str]:
        """指定オブジェクトのカウンター一覧を取得"""
        if not HAS_PDH:
            return []
        
        try:
            counters = win32pdh.EnumObjectItems(None, None, object_name, 0)
            return counters[0] if counters else []  # counters[0]がカウンター名のリスト
        except Exception as e:
            return []
    
    def get_object_instances(self, object_name: str) -> List[str]:
        """指定オブジェクトのインスタンス一覧を取得"""
        if not HAS_PDH:
            return []
        
        try:
            items = win32pdh.EnumObjectItems(None, None, object_name, 0)
            return items[1] if items and len(items) > 1 else []  # items[1]がインスタンス名のリスト
        except Exception as e:
            return []
    
    def analyze_object_details(self, object_name: str) -> Dict:
        """オブジェクトの詳細分析"""
        counters = self.get_object_counters(object_name)
        instances = self.get_object_instances(object_name)
        
        # NPU/AI関連のカウンターを検索
        ai_counters = []
        for counter in counters:
            counter_lower = counter.lower()
            if any(kw in counter_lower for kw in ['npu', 'ai', 'neural', 'boost', 'accelerator', 'ml']):
                ai_counters.append(counter)
        
        # NPU/AI関連のインスタンスを検索
        ai_instances = []
        for instance in instances:
            instance_lower = instance.lower()
            if any(kw in instance_lower for kw in ['npu', 'ai', 'neural', 'boost', 'accelerator', 'ml']):
                ai_instances.append(instance)
        
        return {
            'object_name': object_name,
            'total_counters': len(counters),
            'total_instances': len(instances),
            'ai_counters': ai_counters,
            'ai_instances': ai_instances,
            'all_counters': counters[:10],  # 最初の10個のみ
            'all_instances': instances[:10]  # 最初の10個のみ
        }
    
    def test_counter_paths(self, object_name: str, counters: List[str], instances: List[str]) -> List[str]:
        """カウンターパスの動作テスト"""
        working_paths = []
        
        # インスタンスがない場合のパス
        if not instances:
            for counter in counters[:3]:  # 最初の3個をテスト
                path = f"\\{object_name}\\{counter}"
                if self._test_single_path(path):
                    working_paths.append(path)
        else:
            # インスタンスがある場合のパス
            for instance in instances[:2]:  # 最初の2個のインスタンス
                for counter in counters[:3]:  # 最初の3個のカウンター
                    path = f"\\{object_name}({instance})\\{counter}"
                    if self._test_single_path(path):
                        working_paths.append(path)
        
        return working_paths
    
    def _test_single_path(self, counter_path: str) -> bool:
        """単一カウンターパスのテスト"""
        try:
            query = win32pdh.OpenQuery()
            counter = win32pdh.AddCounter(query, counter_path)
            
            win32pdh.CollectQueryData(query)
            time.sleep(0.1)
            win32pdh.CollectQueryData(query)
            
            t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
            
            win32pdh.CloseQuery(query)
            return True
        except:
            return False
    
    def search_with_expand_counter_path(self) -> Dict[str, List[str]]:
        """ExpandCounterPathを使用した包括的検索"""
        print("\nUsing ExpandCounterPath for comprehensive search...")
        
        patterns = [
            # 基本的なNPU/AIパターン
            r"\*NPU*\*",
            r"\*AI*\*",
            r"\*Neural*\*",
            r"\*Boost*\*",
            r"\*Accelerator*\*",
            r"\*Inference*\*",
            
            # エンジン系
            r"\*Engine*\*",
            r"\Engine*\*",
            r"\GPU Engine*\*",
            r"\NPU Engine*\*",
            
            # プロセッサー系
            r"\Processor*\*",
            r"\*Processor*\*",
            r"\Neural*Processor*\*",
            
            # メモリ系
            r"\*Memory*\*",
            r"\NPU*Memory*\*",
            r"\GPU*Memory*\*",
            
            # 電力系
            r"\Power*\*",
            r"\*Power*\*",
            
            # その他
            r"\*ML*\*",
            r"\*DirectML*\*",
            r"\*WinML*\*"
        ]
        
        found_paths = defaultdict(list)
        
        for pattern in patterns:
            try:
                paths = win32pdh.ExpandCounterPath(pattern)
                if paths:
                    print(f"Pattern '{pattern}': {len(paths)} matches")
                    found_paths[pattern] = list(paths)
                    
                    # NPU/AI関連の可能性が高いパスを抽出
                    ai_related = []
                    for path in paths:
                        path_lower = path.lower()
                        if any(kw in path_lower for kw in ['npu', 'ai', 'neural', 'boost', 'accelerator']):
                            ai_related.append(path)
                    
                    if ai_related:
                        print(f"  AI/NPU related: {len(ai_related)} paths")
                        for path in ai_related[:3]:
                            print(f"    {path}")
                        if len(ai_related) > 3:
                            print(f"    ... and {len(ai_related) - 3} more")
            except Exception as e:
                continue
        
        return dict(found_paths)
    
    def comprehensive_search(self):
        """包括的なNPU/AI オブジェクト検索"""
        print("=" * 80)
        print(" Comprehensive NPU/AI Performance Object Search")
        print("=" * 80)
        
        if not HAS_PDH:
            print("ERROR: win32pdh is not available")
            return
        
        # 1. 全オブジェクト列挙
        all_objects = self.enumerate_all_performance_objects()
        
        # 2. キーワード検索
        keyword_matches = self.search_objects_by_keywords(all_objects)
        
        print(f"\nKeyword Search Results:")
        print("-" * 50)
        
        for keyword, objects in keyword_matches.items():
            if objects:
                print(f"\nKeyword '{keyword}': {len(objects)} objects")
                for obj in objects:
                    print(f"  - {obj}")
        
        # 3. 有力オブジェクトの詳細分析
        promising_objects = set()
        for objects in keyword_matches.values():
            promising_objects.update(objects)
        
        if promising_objects:
            print(f"\n{'='*60}")
            print(f" Detailed Analysis of {len(promising_objects)} Promising Objects")
            print(f"{'='*60}")
            
            for obj in sorted(promising_objects):
                print(f"\nAnalyzing: {obj}")
                details = self.analyze_object_details(obj)
                
                print(f"  Counters: {details['total_counters']} total")
                print(f"  Instances: {details['total_instances']} total")
                
                if details['ai_counters']:
                    print(f"  AI/NPU Counters: {len(details['ai_counters'])}")
                    for counter in details['ai_counters']:
                        print(f"    - {counter}")
                
                if details['ai_instances']:
                    print(f"  AI/NPU Instances: {len(details['ai_instances'])}")
                    for instance in details['ai_instances']:
                        print(f"    - {instance}")
                
                # パステスト
                working_paths = self.test_counter_paths(
                    obj, 
                    details['all_counters'], 
                    details['all_instances']
                )
                
                if working_paths:
                    print(f"  Working Paths: {len(working_paths)}")
                    for path in working_paths:
                        print(f"    ✓ {path}")
        
        # 4. ExpandCounterPath検索
        expand_results = self.search_with_expand_counter_path()
        
        # 5. 結論
        print(f"\n{'='*80}")
        print(" SEARCH CONCLUSION")
        print(f"{'='*80}")
        
        total_objects_found = len(promising_objects)
        total_patterns_found = len([p for p in expand_results.values() if p])
        
        print(f"Objects with NPU/AI keywords: {total_objects_found}")
        print(f"Patterns with matches: {total_patterns_found}")
        
        if total_objects_found == 0 and total_patterns_found == 0:
            print("\n❌ No direct NPU/AI performance objects found")
            print("This confirms that NPU-specific counters are not exposed in current Windows version")
            self._suggest_alternatives()
        else:
            print(f"\n✅ Found potential NPU/AI monitoring capabilities")
            print("Further investigation of found objects recommended")
    
    def _suggest_alternatives(self):
        """代替手段の提案"""
        print(f"\n{'='*60}")
        print(" Alternative Monitoring Approaches")
        print(f"{'='*60}")
        
        print("Since direct NPU counters are not available, consider:")
        print("1. Process-based monitoring (AI applications)")
        print("2. GPU Engine utilization patterns")
        print("3. CPU usage reduction during AI tasks")
        print("4. Power consumption analysis")
        print("5. DirectML/WinML API-level monitoring")

def main():
    """メイン関数"""
    print("Win32 PDH NPU/AI Object Search Tool")
    print("Comprehensive search for NPU and AI-related performance objects")
    print()
    
    searcher = PDHObjectSearcher()
    searcher.comprehensive_search()

if __name__ == "__main__":
    main()