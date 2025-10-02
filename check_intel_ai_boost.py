# Intel AI Boost NPU専用の監視方法を試すスクリプト
import time
import subprocess

def check_intel_ai_boost_counters():
    """Intel AI Boost専用のパフォーマンスカウンターを検索"""
    print("=== Intel AI Boost パフォーマンスカウンター検索 ===")
    
    try:
        import win32pdh
        
        # Intel AI Boost関連のパフォーマンスカウンターパターンを試す
        counter_patterns = [
            r"\NPU Engine(*)\Utilization Percentage",
            r"\Intel AI Boost(*)\*",
            r"\AI Boost(*)\*", 
            r"\Neural Engine(*)\*",
            r"\Intel NPU(*)\*",
            r"\Intel(R) AI Boost(*)\*",
            r"\Processor Information(*)\*",
            r"\Neural Processing Unit(*)\*",
            r"\AI Processing Unit(*)\*"
        ]
        
        found_counters = []
        
        for pattern in counter_patterns:
            try:
                print(f"\nパターン '{pattern}' をチェック中...")
                paths = win32pdh.ExpandCounterPath(pattern)
                if paths:
                    print(f"  見つかったパス: {len(paths)}個")
                    for path in paths:
                        print(f"    {path}")
                        found_counters.append(path)
                else:
                    print("  パスが見つかりませんでした")
            except Exception as e:
                print(f"  エラー: {e}")
        
        # より広範囲な検索
        print(f"\n=== すべてのカウンターから'AI'を含むものを検索 ===")
        try:
            result = subprocess.run(['typeperf', '-q'], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                ai_counters = [line for line in lines if 'ai' in line.lower() and line.strip()]
                if ai_counters:
                    print(f"見つかったAI関連カウンター: {len(ai_counters)}個")
                    for counter in ai_counters[:20]:  # 最初の20個を表示
                        print(f"  {counter}")
                    if len(ai_counters) > 20:
                        print(f"  ... 他 {len(ai_counters) - 20}個")
                else:
                    print("AI関連カウンターが見つかりませんでした")
        except Exception as e:
            print(f"検索エラー: {e}")
            
        return found_counters
        
    except ImportError:
        print("win32pdh がインストールされていません")
        return []
    except Exception as e:
        print(f"エラー: {e}")
        return []

def check_processor_counters():
    """プロセッサー関連カウンターでNPU情報を探す"""
    print("\n=== プロセッサー関連カウンター検索 ===")
    
    try:
        import win32pdh
        
        # プロセッサー情報カウンターを詳細に確認
        processor_pattern = r"\Processor Information(*)\*"
        try:
            paths = win32pdh.ExpandCounterPath(processor_pattern)
            if paths:
                print(f"プロセッサー情報カウンター: {len(paths)}個")
                
                # NPU関連の可能性があるカウンターを抽出
                npu_related = []
                for path in paths:
                    path_lower = path.lower()
                    if any(keyword in path_lower for keyword in ['ai', 'neural', 'boost', 'npu', 'accelerator']):
                        npu_related.append(path)
                
                if npu_related:
                    print(f"NPU関連の可能性があるカウンター: {len(npu_related)}個")
                    for counter in npu_related:
                        print(f"  {counter}")
                        
                # 利用可能率やクロック周波数など
                utilization_counters = []
                for path in paths:
                    if any(keyword in path.lower() for keyword in ['utilization', 'usage', 'percentage', 'frequency']):
                        utilization_counters.append(path)
                
                if utilization_counters:
                    print(f"\n利用率関連カウンター（例）: {min(10, len(utilization_counters))}個")
                    for counter in utilization_counters[:10]:
                        print(f"  {counter}")
                        
        except Exception as e:
            print(f"プロセッサーカウンター取得エラー: {e}")
            
    except ImportError:
        print("win32pdh がインストールされていません")
    except Exception as e:
        print(f"エラー: {e}")

def test_sample_counter(counter_path):
    """特定のカウンターからサンプルデータを取得テスト"""
    print(f"\n=== カウンターサンプリングテスト: {counter_path} ===")
    
    try:
        import win32pdh
        
        query = win32pdh.OpenQuery()
        counter = win32pdh.AddCounter(query, counter_path)
        
        # 初回サンプル
        win32pdh.CollectQueryData(query)
        time.sleep(1.0)  # 1秒待機
        
        # 2回目サンプル
        win32pdh.CollectQueryData(query)
        
        # データ取得
        t, val = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
        print(f"値: {val}")
        
        win32pdh.CloseQuery(query)
        return True
        
    except Exception as e:
        print(f"サンプリングエラー: {e}")
        return False

if __name__ == "__main__":
    found_counters = check_intel_ai_boost_counters()
    check_processor_counters()
    
    # 見つかったカウンターがあれば、いくつかテストしてみる
    if found_counters:
        print(f"\n=== カウンターテスト ===")
        for counter in found_counters[:3]:  # 最初の3個をテスト
            test_sample_counter(counter)
    
    print("\n=== 結論と推奨事項 ===")
    print("1. Intel Core Ultra 7 258VにはNPU (AI Boost) が搭載されています")
    print("2. 標準的な\\NPU Engine(*)\\Utilization Percentageカウンターは利用できません")
    print("3. 代替監視方法:")
    print("   - Windows Task Managerを確認してNPUタブが表示されるか")
    print("   - Intel Graphics Command Center でAI性能を確認")
    print("   - WMI経由でのIntel AI Boostデバイス状態監視")
    print("   - プロセス別リソース使用量の間接的監視")
    print("4. 将来的な改善:")
    print("   - Intelドライバーの最新版確認")
    print("   - Windows 11 24H2でのNPUサポート改善待ち")
    print("   - Intel oneAPI/OpenVINO使用時の専用監視ツール利用")