#!/usr/bin/env python3
"""
ETW プロバイダー調査スクリプト (WPT不要)
logman を使用してNPU/AI関連のETWプロバイダーを発見
"""

import subprocess
import re
from typing import List, Dict, Tuple
from collections import defaultdict

class ETWProviderInvestigator:
    """ETW プロバイダー調査クラス"""
    
    def __init__(self):
        self.all_providers = []
        self.categorized_providers = {
            'npu': [],
            'ai': [],
            'gpu': [],
            'intel': [],
            'compute': [],
            'directml': [],
            'other_interesting': []
        }
    
    def discover_all_etw_providers(self) -> List[Dict[str, str]]:
        """すべてのETWプロバイダーを発見"""
        print("Discovering all ETW providers using logman...")
        
        try:
            # logman query providers でETWプロバイダー一覧を取得
            result = subprocess.run(
                ["logman", "query", "providers"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"Error running logman: {result.stderr}")
                return []
            
            providers = []
            lines = result.stdout.split('\n')
            
            print(f"Raw output has {len(lines)} lines")
            
            for line in lines[3:]:  # Skip header lines
                line = line.strip()
                if not line or line.startswith('---') or 'Provider' in line:
                    continue
                
                # プロバイダー行の解析
                # 形式: Provider Name {GUID}
                guid_match = re.search(r'\{([^}]+)\}', line)
                if guid_match:
                    guid = guid_match.group(1)
                    provider_name = line[:guid_match.start()].strip()
                    
                    if provider_name:
                        providers.append({
                            'name': provider_name,
                            'guid': guid,
                            'full_line': line
                        })
                elif line:
                    # GUID がない場合
                    providers.append({
                        'name': line,
                        'guid': '',
                        'full_line': line
                    })
            
            print(f"✓ Discovered {len(providers)} ETW providers")
            self.all_providers = providers
            return providers
            
        except Exception as e:
            print(f"Error discovering ETW providers: {e}")
            return []
    
    def categorize_providers(self, providers: List[Dict[str, str]]):
        """プロバイダーをカテゴリ別に分類"""
        print("\nCategorizing providers by relevance...")
        
        keywords = {
            'npu': ['npu', 'neural processing', 'ai boost', 'neural engine'],
            'ai': ['ai', 'ml', 'machine learning', 'inference', 'winml', 'onnx', 'cognitive'],
            'gpu': ['gpu', 'graphics', 'display', 'render', 'd3d', 'directx', 'dxgi', 'dxgk'],
            'intel': ['intel', 'igfx', 'gfx'],
            'compute': ['compute', 'opencl', 'cuda', 'hlsl'],
            'directml': ['directml', 'dml', 'tensorfl', 'pytorch'],
        }
        
        for provider in providers:
            name_lower = provider['name'].lower()
            categorized = False
            
            for category, category_keywords in keywords.items():
                if any(keyword in name_lower for keyword in category_keywords):
                    self.categorized_providers[category].append(provider)
                    categorized = True
                    break
            
            # 興味深いキーワードをチェック
            interesting_keywords = [
                'power', 'thermal', 'performance', 'kernel', 'driver', 
                'hardware', 'device', 'pci', 'acpi', 'memory'
            ]
            
            if not categorized and any(keyword in name_lower for keyword in interesting_keywords):
                self.categorized_providers['other_interesting'].append(provider)
    
    def display_categorized_results(self):
        """カテゴリ別結果表示"""
        print(f"\n{'='*80}")
        print(" ETW PROVIDER CATEGORIZATION RESULTS")
        print(f"{'='*80}")
        
        category_names = {
            'npu': 'NPU/Neural Processing',
            'ai': 'AI/Machine Learning', 
            'gpu': 'GPU/Graphics',
            'intel': 'Intel Hardware',
            'compute': 'Compute/Parallel Processing',
            'directml': 'DirectML/AI Frameworks',
            'other_interesting': 'Other Potentially Relevant'
        }
        
        total_relevant = 0
        
        for category, providers in self.categorized_providers.items():
            if providers:
                print(f"\n🔍 {category_names[category]} ({len(providers)} providers):")
                total_relevant += len(providers)
                
                for i, provider in enumerate(providers[:10]):  # 最初の10個を表示
                    guid_info = f" [{provider['guid'][:8]}...]" if provider['guid'] else ""
                    print(f"  {i+1:2d}. {provider['name']}{guid_info}")
                
                if len(providers) > 10:
                    print(f"      ... and {len(providers) - 10} more")
        
        print(f"\n📊 Summary:")
        print(f"  Total ETW providers: {len(self.all_providers)}")
        print(f"  Potentially relevant: {total_relevant}")
        print(f"  Relevance ratio: {total_relevant/len(self.all_providers)*100:.1f}%")
    
    def find_most_promising_npu_providers(self) -> List[Dict[str, str]]:
        """最も有望なNPU関連プロバイダーを特定"""
        print(f"\n{'='*60}")
        print(" MOST PROMISING NPU PROVIDERS")
        print(f"{'='*60}")
        
        promising_providers = []
        
        # 直接的NPU関連
        npu_direct = self.categorized_providers['npu']
        if npu_direct:
            print(f"🎯 Direct NPU providers ({len(npu_direct)}):")
            for provider in npu_direct:
                print(f"  ⭐ {provider['name']}")
                promising_providers.append(provider)
        
        # Intel + AI関連
        intel_providers = self.categorized_providers['intel']
        ai_providers = self.categorized_providers['ai']
        
        intel_ai_intersection = []
        for intel_provider in intel_providers:
            intel_name_lower = intel_provider['name'].lower()
            if any(ai_kw in intel_name_lower for ai_kw in ['ai', 'ml', 'neural', 'boost']):
                intel_ai_intersection.append(intel_provider)
        
        if intel_ai_intersection:
            print(f"\n🎯 Intel AI-related providers ({len(intel_ai_intersection)}):")
            for provider in intel_ai_intersection:
                print(f"  ⭐ {provider['name']}")
                promising_providers.extend(intel_ai_intersection)
        
        # DirectML/AI Framework関連
        directml_providers = self.categorized_providers['directml']
        if directml_providers:
            print(f"\n🎯 DirectML/AI Framework providers ({len(directml_providers)}):")
            for provider in directml_providers:
                print(f"  ⭐ {provider['name']}")
                promising_providers.extend(directml_providers)
        
        # GPU Compute関連（NPU候補）
        gpu_providers = self.categorized_providers['gpu']
        gpu_compute = []
        for provider in gpu_providers:
            name_lower = provider['name'].lower()
            if any(kw in name_lower for kw in ['compute', 'scheduler', 'kernel']):
                gpu_compute.append(provider)
        
        if gpu_compute:
            print(f"\n🎯 GPU Compute providers (NPU candidates) ({len(gpu_compute)}):")
            for provider in gpu_compute[:5]:  # 最初の5個
                print(f"  ⭐ {provider['name']}")
            if len(gpu_compute) > 5:
                print(f"      ... and {len(gpu_compute) - 5} more")
            promising_providers.extend(gpu_compute)
        
        if not promising_providers:
            print("❌ No directly promising NPU providers found")
            print("💡 Consider monitoring GPU compute and AI framework providers")
        
        return promising_providers
    
    def generate_etw_monitoring_commands(self, promising_providers: List[Dict[str, str]]) -> List[str]:
        """ETW監視コマンドを生成"""
        print(f"\n{'='*60}")
        print(" ETW MONITORING COMMANDS")
        print(f"{'='*60}")
        
        if not promising_providers:
            print("No specific providers available for ETW monitoring")
            return []
        
        commands = []
        
        print("🛠 PowerShell commands for ETW tracing:")
        print()
        
        # 個別プロバイダー監視コマンド
        for i, provider in enumerate(promising_providers[:3]):  # 最初の3個
            if provider['guid']:
                cmd = f'logman start "NPU_Monitor_{i+1}" -p "{{{provider["guid"]}}}" -o npu_trace_{i+1}.etl -ets'
                commands.append(cmd)
                print(f"# Monitor {provider['name']}")
                print(f"{cmd}")
                print(f'logman stop "NPU_Monitor_{i+1}" -ets')
                print()
        
        # 複合監視コマンド
        if len(promising_providers) > 1:
            print("# Combined monitoring (multiple providers)")
            guid_list = []
            for provider in promising_providers[:5]:  # 最初の5個
                if provider['guid']:
                    guid_list.append(f'"{{{provider["guid"]}}}"')
            
            if guid_list:
                combined_cmd = f'logman start "NPU_Combined" -p {" -p ".join(guid_list)} -o npu_combined_trace.etl -ets'
                commands.append(combined_cmd)
                print(combined_cmd)
                print('logman stop "NPU_Combined" -ets')
                print()
        
        # 分析コマンド
        print("🔍 Trace analysis commands:")
        print("# Convert ETL to CSV for analysis")
        print("wevtutil qe npu_trace_1.etl /lf:true /f:text > npu_events.txt")
        print()
        print("# Use PowerShell for ETW analysis")
        print("Get-WinEvent -Path npu_trace_1.etl | Where-Object {$_.LevelDisplayName -eq 'Information'}")
        
        return commands
    
    def comprehensive_etw_investigation(self):
        """包括的ETW調査"""
        print("=" * 80)
        print(" COMPREHENSIVE ETW PROVIDER INVESTIGATION FOR NPU")
        print("=" * 80)
        
        # 1. すべてのETWプロバイダーを発見
        providers = self.discover_all_etw_providers()
        
        if not providers:
            print("❌ Could not discover ETW providers")
            return
        
        # 2. プロバイダーをカテゴリ別に分類
        self.categorize_providers(providers)
        
        # 3. カテゴリ別結果表示
        self.display_categorized_results()
        
        # 4. 最も有望なNPUプロバイダーを特定
        promising_providers = self.find_most_promising_npu_providers()
        
        # 5. ETW監視コマンドを生成
        commands = self.generate_etw_monitoring_commands(promising_providers)
        
        # 6. 結論と推奨事項
        print(f"\n{'='*60}")
        print(" CONCLUSIONS AND RECOMMENDATIONS")
        print(f"{'='*60}")
        
        if promising_providers:
            print("✅ Found potentially useful ETW providers for NPU monitoring")
            print("💡 Recommendations:")
            print("  1. Use the generated logman commands to start ETW tracing")
            print("  2. Run AI workloads while tracing is active")
            print("  3. Analyze ETL files for NPU-related events")
            print("  4. Correlate events with known AI application activity")
        else:
            print("⚠ No direct NPU ETW providers found")
            print("💡 Alternative approach:")
            print("  1. Monitor GPU compute providers for integrated NPU activity")
            print("  2. Track DirectML and AI framework events")
            print("  3. Use process and power monitoring as fallback")
        
        print(f"\n📋 Next steps:")
        print("  1. Install Windows Performance Toolkit for advanced analysis")
        print("  2. Use generated commands to collect ETW traces")
        print("  3. Correlate ETW events with NPU workload patterns")
        print("  4. Develop custom ETW analysis tools for NPU monitoring")

def main():
    """メイン関数"""
    print("ETW Provider Investigation for NPU Monitoring")
    print("Discovering NPU/AI-related Event Tracing for Windows providers")
    print()
    
    investigator = ETWProviderInvestigator()
    investigator.comprehensive_etw_investigation()

if __name__ == "__main__":
    main()