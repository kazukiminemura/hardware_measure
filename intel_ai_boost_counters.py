#!/usr/bin/env python3
"""
Intel AI Boost NPU Performance Counters 調査スクリプト
win32pdhを使用してIntel AI Boost NPUで利用可能なコレクタ一覧を表示
"""

import subprocess
import time
from typing import List, Dict, Any

# ----- Dependencies -----
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

class IntelAIBoostCounterInvestigator:
    """Intel AI Boost NPU専用のパフォーマンスカウンタ調査クラス"""
    
    def __init__(self):
        self.ai_boost_detected = self._detect_intel_ai_boost()
        self.available_counters = []
        self.counter_patterns = [
            # NPU関連の基本パターン
            r"\NPU Engine(*)\*",
            r"\NPU Engine(*)\Utilization Percentage",
            r"\NPU Process Memory(*)\*",
            r"\NPU Adapter Memory(*)\*",
            
            # Intel AI Boost専用パターン
            r"\Intel AI Boost(*)\*",
            r"\AI Boost(*)\*",
            r"\Intel(R) AI Boost(*)\*",
            r"\Neural Processing Unit(*)\*",
            r"\Neural Engine(*)\*",
            r"\AI Processing Unit(*)\*",
            r"\AI Accelerator(*)\*",
            
            # プロセッサー情報内のNPU関連
            r"\Processor Information(*)\*AI*",
            r"\Processor Information(*)\*Neural*",
            r"\Processor Information(*)\*NPU*",
            
            # GPU Engine内のNPU関連（統合デバイスの可能性）
            r"\GPU Engine(*)\*AI*",
            r"\GPU Engine(*)\*Neural*",
            r"\GPU Engine(*)\*NPU*",
            
            # システムレベルの電力・温度（NPU関連）
            r"\Thermal Zone Information(*)\*",
            r"\Power Meter(*)\*",
        ]
    
    def _detect_intel_ai_boost(self) -> bool:
        """Intel AI Boost NPUの存在確認"""
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
    
    def investigate_pdh_counters(self):
        """PDHカウンタの詳細調査"""
        print("=" * 80)
        print(" Intel AI Boost NPU - PDH Performance Counters Investigation")
        print("=" * 80)
        
        # Intel AI Boost検出状況
        if self.ai_boost_detected:
            print("✓ Intel AI Boost NPU: DETECTED")
        else:
            print("✗ Intel AI Boost NPU: NOT DETECTED")
            print("  Warning: This investigation may not find NPU-specific counters")
        
        print(f"✓ win32pdh: {'Available' if HAS_PDH else 'NOT Available'}")
        print()
        
        if not HAS_PDH:
            print("ERROR: win32pdh is not available. Please install pywin32:")
            print("  pip install pywin32")
            return
        
        # パターン別調査
        print("Investigating Performance Counter Patterns...")
        print("-" * 60)
        
        all_found_counters = []
        
        for pattern in self.counter_patterns:
            print(f"\nPattern: {pattern}")
            found_counters = self._expand_counter_pattern(pattern)
            
            if found_counters:
                print(f"  ✓ Found {len(found_counters)} counters:")
                for counter in found_counters[:10]:  # 最初の10個のみ表示
                    print(f"    {counter}")
                if len(found_counters) > 10:
                    print(f"    ... and {len(found_counters) - 10} more")
                
                all_found_counters.extend(found_counters)
            else:
                print("  ✗ No counters found")
        
        # 重複除去
        unique_counters = list(set(all_found_counters))
        
        print(f"\n{'='*60}")
        print(f" Summary: Found {len(unique_counters)} unique counters")
        print(f"{'='*60}")
        
        if unique_counters:
            self._test_counter_sampling(unique_counters[:5])  # 最初の5個をテスト
        else:
            print("No NPU-related performance counters found.")
            self._suggest_alternatives()
    
    def _expand_counter_pattern(self, pattern: str) -> List[str]:
        """パフォーマンスカウンタパターンを展開"""
        try:
            paths = win32pdh.ExpandCounterPath(pattern)
            return list(paths) if paths else []
        except Exception as e:
            return []
    
    def _test_counter_sampling(self, counters: List[str]):
        """カウンタからのサンプリングテスト"""
        print(f"\nTesting Counter Sampling (first 5 counters)...")
        print("-" * 50)
        
        for counter_path in counters:
            print(f"\nTesting: {counter_path}")
            success = self._test_single_counter(counter_path)
            if success:
                print("  ✓ Sampling successful")
            else:
                print("  ✗ Sampling failed")
    
    def _test_single_counter(self, counter_path: str) -> bool:
        """単一カウンタのサンプリングテスト"""
        try:
            query = win32pdh.OpenQuery()
            counter = win32pdh.AddCounter(query, counter_path)
            
            # 初回収集
            win32pdh.CollectQueryData(query)
            time.sleep(0.5)  # 0.5秒待機
            
            # 2回目収集
            win32pdh.CollectQueryData(query)
            
            # 値取得
            t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
            print(f"    Value: {val}")
            
            win32pdh.CloseQuery(query)
            return True
            
        except Exception as e:
            print(f"    Error: {e}")
            return False
    
    def investigate_all_counters_with_keywords(self):
        """全パフォーマンスカウンタからキーワード検索"""
        print(f"\n{'='*80}")
        print(" Comprehensive Counter Search with AI/NPU Keywords")
        print(f"{'='*80}")
        
        keywords = [
            'ai', 'npu', 'neural', 'boost', 'accelerator', 'inference',
            'ml', 'machine learning', 'deep learning', 'intel ai'
        ]
        
        print("Searching all performance counters for NPU/AI keywords...")
        print("This may take a moment...\n")
        
        try:
            # typeperfコマンドで全カウンタリストを取得
            result = subprocess.run(
                ['typeperf', '-q'], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"Error running typeperf: {result.stderr}")
                return
            
            all_counters = result.stdout.split('\n')
            print(f"Total counters found: {len(all_counters)}")
            
            # キーワード検索
            matched_counters = []
            for keyword in keywords:
                keyword_matches = [
                    counter for counter in all_counters 
                    if keyword.lower() in counter.lower() and counter.strip()
                ]
                
                if keyword_matches:
                    print(f"\nKeyword '{keyword}': {len(keyword_matches)} matches")
                    for match in keyword_matches[:5]:  # 最初の5個のみ表示
                        print(f"  {match}")
                    if len(keyword_matches) > 5:
                        print(f"  ... and {len(keyword_matches) - 5} more")
                    
                    matched_counters.extend(keyword_matches)
                else:
                    print(f"Keyword '{keyword}': No matches")
            
            # 重複除去
            unique_matches = list(set(matched_counters))
            
            if unique_matches:
                print(f"\nTotal unique AI/NPU related counters: {len(unique_matches)}")
                self._analyze_matched_counters(unique_matches)
            else:
                print("\nNo AI/NPU related counters found in comprehensive search.")
                
        except subprocess.TimeoutExpired:
            print("Timeout occurred while listing counters")
        except FileNotFoundError:
            print("typeperf command not found")
        except Exception as e:
            print(f"Error in comprehensive search: {e}")
    
    def _analyze_matched_counters(self, counters: List[str]):
        """マッチしたカウンタの分析"""
        print(f"\nAnalyzing matched counters...")
        print("-" * 40)
        
        # カテゴリ別に分類
        categories = {
            'NPU Engine': [c for c in counters if 'npu engine' in c.lower()],
            'GPU Engine': [c for c in counters if 'gpu engine' in c.lower() and any(kw in c.lower() for kw in ['ai', 'neural', 'npu'])],
            'Processor': [c for c in counters if 'processor' in c.lower()],
            'Memory': [c for c in counters if 'memory' in c.lower()],
            'Thermal': [c for c in counters if 'thermal' in c.lower()],
            'Power': [c for c in counters if 'power' in c.lower()],
            'Other': []
        }
        
        # その他カテゴリに分類されないものを追加
        categorized = set()
        for cat_counters in categories.values():
            categorized.update(cat_counters)
        
        categories['Other'] = [c for c in counters if c not in categorized]
        
        for category, cat_counters in categories.items():
            if cat_counters:
                print(f"\n{category} ({len(cat_counters)} counters):")
                for counter in cat_counters[:3]:  # 最初の3個のみ表示
                    print(f"  {counter}")
                if len(cat_counters) > 3:
                    print(f"  ... and {len(cat_counters) - 3} more")
    
    def _suggest_alternatives(self):
        """代替監視方法の提案"""
        print(f"\n{'='*60}")
        print(" Alternative Monitoring Suggestions")
        print(f"{'='*60}")
        
        print("Since no direct NPU performance counters were found, consider:")
        print()
        
        print("1. Task Manager Monitoring:")
        print("   - Open Task Manager > Performance tab")
        print("   - Check if NPU appears as a separate graph")
        print()
        
        print("2. Windows Performance Monitor (perfmon):")
        print("   - Run 'perfmon' from Start menu")
        print("   - Look for NPU-related counter sets")
        print()
        
        print("3. Intel Graphics Command Center:")
        print("   - Install from Microsoft Store")
        print("   - Check for AI/NPU performance metrics")
        print()
        
        print("4. Process-based Monitoring:")
        print("   - Monitor AI application CPU usage reduction")
        print("   - Detect ONNX Runtime / DirectML processes")
        print()
        
        print("5. DirectML API Monitoring:")
        print("   - Use DirectML performance queries")
        print("   - Monitor GPU Engine usage patterns")
    
    def create_comprehensive_report(self):
        """包括的な調査レポート作成"""
        print("Creating comprehensive Intel AI Boost NPU investigation report...")
        
        # 基本検出
        self.investigate_pdh_counters()
        
        # 包括的検索
        self.investigate_all_counters_with_keywords()
        
        # 結論とレコメンデーション
        print(f"\n{'='*80}")
        print(" INVESTIGATION CONCLUSION")
        print(f"{'='*80}")
        
        if self.ai_boost_detected:
            print("✓ Intel AI Boost NPU hardware is present on this system")
        else:
            print("✗ Intel AI Boost NPU hardware not detected")
        
        print("\nFindings:")
        print("- Direct NPU performance counters may not be exposed in current Windows versions")
        print("- Windows 11 24H2 and later may provide better NPU counter support")
        print("- Alternative monitoring methods are recommended for NPU activity tracking")
        
        print("\nRecommended Next Steps:")
        print("1. Update to the latest Windows 11 version")
        print("2. Install latest Intel graphics drivers")
        print("3. Use process-based AI activity monitoring")
        print("4. Implement DirectML usage pattern analysis")

def main():
    """メイン関数"""
    print("Intel AI Boost NPU Performance Counters Investigation")
    print("Using win32pdh to discover available monitoring capabilities")
    print()
    
    investigator = IntelAIBoostCounterInvestigator()
    investigator.create_comprehensive_report()

if __name__ == "__main__":
    main()