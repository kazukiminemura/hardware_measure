#!/usr/bin/env python3
"""
Windows Performance Toolkit (WPT) を使用したNPU監視調査
ETW (Event Tracing for Windows) プロバイダーでNPU活動を検出
"""

import subprocess
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class WPTResult:
    """WPT調査結果"""
    tool_available: bool
    etw_providers: List[str]
    npu_related_providers: List[str]
    gpu_providers: List[str]
    ai_related_providers: List[str]
    trace_results: Optional[Dict]

class WPTNPUInvestigator:
    """Windows Performance Toolkit NPU調査クラス"""
    
    def __init__(self):
        self.wpt_path = self._find_wpt_installation()
        self.temp_trace_file = "npu_trace.etl"
        
    def _find_wpt_installation(self) -> Optional[Path]:
        """WPTインストール場所を検索"""
        possible_paths = [
            # Windows SDK paths
            Path(r"C:\Program Files (x86)\Windows Kits\10\bin\x64"),
            Path(r"C:\Program Files\Windows Kits\10\bin\x64"),
            Path(r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64"),
            Path(r"C:\Program Files\Windows Kits\10\bin\10.0.26100.0\x64"),
            
            # WPT standalone installation
            Path(r"C:\Program Files\Windows Performance Toolkit"),
            Path(r"C:\Program Files (x86)\Windows Performance Toolkit"),
            
            # ADK installation
            Path(r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Windows Performance Toolkit"),
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "wpr.exe").exists():
                print(f"✓ Found WPT at: {path}")
                return path
        
        print("✗ Windows Performance Toolkit not found")
        print("Please install Windows ADK or Windows SDK")
        return None
    
    def check_wpt_availability(self) -> bool:
        """WPTツールの利用可能性確認"""
        if not self.wpt_path:
            return False
        
        tools = ["wpr.exe", "wpa.exe", "xperf.exe"]
        available_tools = []
        
        for tool in tools:
            tool_path = self.wpt_path / tool
            if tool_path.exists():
                available_tools.append(tool)
                print(f"✓ {tool} available")
            else:
                print(f"✗ {tool} not found")
        
        return len(available_tools) > 0
    
    def discover_etw_providers(self) -> List[str]:
        """ETW プロバイダーを発見"""
        print("\nDiscovering ETW providers...")
        
        if not self.wpt_path:
            return []
        
        try:
            # logman query providers でETWプロバイダー一覧を取得
            result = subprocess.run(
                ["logman", "query", "providers"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"Error running logman: {result.stderr}")
                return []
            
            providers = []
            lines = result.stdout.split('\n')
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('Provider') and not line.startswith('-'):
                    # プロバイダー名を抽出（GUID付きの場合も対応）
                    if '{' in line and '}' in line:
                        # GUID形式の場合
                        parts = line.split()
                        if len(parts) >= 2:
                            provider_name = ' '.join(parts[:-1])  # GUID以外の部分
                            providers.append(provider_name.strip())
                    else:
                        # 通常の名前の場合
                        providers.append(line)
            
            print(f"Found {len(providers)} ETW providers")
            return providers
            
        except Exception as e:
            print(f"Error discovering ETW providers: {e}")
            return []
    
    def find_npu_related_providers(self, providers: List[str]) -> Tuple[List[str], List[str], List[str]]:
        """NPU/AI/GPU関連のETWプロバイダーを特定"""
        print("\nAnalyzing providers for NPU/AI/GPU relevance...")
        
        npu_keywords = ['npu', 'neural', 'ai boost', 'intel ai', 'neural processing']
        ai_keywords = ['ai', 'ml', 'machine learning', 'inference', 'winml', 'directml', 'onnx']
        gpu_keywords = ['gpu', 'graphics', 'display', 'render', 'compute', 'dx', 'directx', 'd3d']
        
        npu_providers = []
        ai_providers = []
        gpu_providers = []
        
        for provider in providers:
            provider_lower = provider.lower()
            
            # NPU関連
            if any(kw in provider_lower for kw in npu_keywords):
                npu_providers.append(provider)
                print(f"  NPU: {provider}")
            
            # AI関連
            elif any(kw in provider_lower for kw in ai_keywords):
                ai_providers.append(provider)
                print(f"  AI:  {provider}")
            
            # GPU関連
            elif any(kw in provider_lower for kw in gpu_keywords):
                gpu_providers.append(provider)
                # GPU関連は多いので最初の5個だけ表示
                if len(gpu_providers) <= 5:
                    print(f"  GPU: {provider}")
        
        if len(gpu_providers) > 5:
            print(f"  GPU: ... and {len(gpu_providers) - 5} more GPU providers")
        
        print(f"\nProvider summary:")
        print(f"  NPU-related: {len(npu_providers)}")
        print(f"  AI-related:  {len(ai_providers)}")
        print(f"  GPU-related: {len(gpu_providers)}")
        
        return npu_providers, ai_providers, gpu_providers
    
    def create_wpt_profile_for_npu(self) -> str:
        """NPU監視用のWPTプロファイルを作成"""
        profile_content = """<?xml version="1.0" encoding="utf-8"?>
<WindowsPerformanceRecorder Version="1.0">
  <Profiles>
    <SystemCollector Id="SystemCollector_NPU" Name="NT Kernel Logger">
      <BufferSize Value="64" />
      <Buffers Value="8" PercentageOfTotalMemory="0" />
    </SystemCollector>
    
    <EventCollector Id="EventCollector_NPU" Name="NPU Event Collector">
      <BufferSize Value="64" />
      <Buffers Value="64" PercentageOfTotalMemory="0" />
    </EventCollector>

    <SystemProvider Id="SystemProvider_NPU">
      <Keywords>
        <Keyword Value="ProcessThread" />
        <Keyword Value="Loader" />
        <Keyword Value="CpuConfig" />
        <Keyword Value="Power" />
        <Keyword Value="IdleState" />
      </Keywords>
    </SystemProvider>

    <EventProvider Id="Microsoft-Windows-Kernel-Power" Name="331C3B3A-2005-44C2-AC5E-77220C37D6B4" />
    <EventProvider Id="Microsoft-Windows-GPU-Scheduler" Name="99134383-5248-4C0F-9E6D-6B52E7E91824" />
    <EventProvider Id="Microsoft-Windows-DxgKrnl" Name="802EC45A-1E99-4B83-9920-87C98277BA9D" />
    <EventProvider Id="Microsoft-Windows-Direct3D" Name="783ACA0A-790E-4D7F-8451-AA850511C6B9" />
    <EventProvider Id="Microsoft-Windows-DirectML" Name="F4B54BF0-3C44-4E5B-A5B0-C70C99D8A715" />

    <Profile Id="NPU_Monitor.Verbose.File" Name="NPU_Monitor" Description="NPU Activity Monitoring" LoggingMode="File" DetailLevel="Verbose">
      <Collectors>
        <SystemCollectorId Value="SystemCollector_NPU">
          <SystemProviderId Value="SystemProvider_NPU" />
        </SystemCollectorId>
        <EventCollectorId Value="EventCollector_NPU">
          <EventProviders>
            <EventProviderId Value="Microsoft-Windows-Kernel-Power" />
            <EventProviderId Value="Microsoft-Windows-GPU-Scheduler" />
            <EventProviderId Value="Microsoft-Windows-DxgKrnl" />
            <EventProviderId Value="Microsoft-Windows-Direct3D" />
            <EventProviderId Value="Microsoft-Windows-DirectML" />
          </EventProviders>
        </EventCollectorId>
      </Collectors>
    </Profile>
  </Profiles>
</WindowsPerformanceRecorder>"""
        
        profile_file = "npu_monitor_profile.wprp"
        
        try:
            with open(profile_file, 'w', encoding='utf-8') as f:
                f.write(profile_content)
            print(f"✓ Created WPT profile: {profile_file}")
            return profile_file
        except Exception as e:
            print(f"✗ Error creating WPT profile: {e}")
            return ""
    
    def run_npu_trace(self, duration: int = 30) -> bool:
        """NPU活動のETWトレースを実行"""
        if not self.wpt_path:
            print("WPT not available for tracing")
            return False
        
        profile_file = self.create_wpt_profile_for_npu()
        if not profile_file:
            return False
        
        wpr_path = self.wpt_path / "wpr.exe"
        
        try:
            print(f"\nStarting ETW trace for {duration} seconds...")
            print("This will monitor NPU/GPU/AI activity at the kernel level")
            
            # トレース開始
            start_cmd = [str(wpr_path), "-start", profile_file, "-filemode"]
            result = subprocess.run(start_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Error starting trace: {result.stderr}")
                return False
            
            print("✓ ETW trace started")
            print(f"Collecting data for {duration} seconds...")
            
            # 指定時間待機
            time.sleep(duration)
            
            # トレース停止
            stop_cmd = [str(wpr_path), "-stop", self.temp_trace_file]
            result = subprocess.run(stop_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Error stopping trace: {result.stderr}")
                return False
            
            print(f"✓ ETW trace completed, saved as: {self.temp_trace_file}")
            
            # ファイルサイズ確認
            if os.path.exists(self.temp_trace_file):
                size_mb = os.path.getsize(self.temp_trace_file) / (1024 * 1024)
                print(f"Trace file size: {size_mb:.2f} MB")
                return True
            
        except Exception as e:
            print(f"Error during ETW tracing: {e}")
            
            # クリーンアップ: トレースが残っている場合は停止
            try:
                subprocess.run([str(wpr_path), "-cancel"], capture_output=True)
            except:
                pass
        
        return False
    
    def analyze_trace_for_npu_activity(self) -> Dict:
        """ETWトレースからNPU活動を分析"""
        if not os.path.exists(self.temp_trace_file):
            print("No trace file available for analysis")
            return {}
        
        print(f"\nAnalyzing ETW trace for NPU activity...")
        
        # 基本的な分析（実際の実装では、より詳細なETW解析が必要）
        analysis_results = {
            "trace_file": self.temp_trace_file,
            "file_size_mb": os.path.getsize(self.temp_trace_file) / (1024 * 1024),
            "analysis_method": "basic_file_analysis",
            "recommendations": []
        }
        
        # ETWトレースの詳細分析には専用ツール（WPA、xperf）が必要
        print("Note: Detailed ETW analysis requires:")
        print("  1. Windows Performance Analyzer (WPA)")
        print("  2. Custom ETW parsing tools")
        print("  3. Specific NPU ETW provider knowledge")
        
        analysis_results["recommendations"] = [
            "Use 'wpa.exe npu_trace.etl' for detailed GUI analysis",
            "Use 'xperf -i npu_trace.etl -a ...' for command-line analysis",
            "Look for GPU, DirectML, and Power events that correlate with NPU activity",
            "Monitor process creation events for AI frameworks"
        ]
        
        return analysis_results
    
    def comprehensive_wpt_investigation(self) -> WPTResult:
        """包括的WPT調査"""
        print("=" * 80)
        print(" WINDOWS PERFORMANCE TOOLKIT NPU INVESTIGATION")
        print("=" * 80)
        
        result = WPTResult(
            tool_available=False,
            etw_providers=[],
            npu_related_providers=[],
            gpu_providers=[],
            ai_related_providers=[],
            trace_results=None
        )
        
        # 1. WPT利用可能性確認
        if not self.check_wpt_availability():
            print("\nWPT is not available. Please install Windows ADK or Windows SDK.")
            return result
        
        result.tool_available = True
        
        # 2. ETWプロバイダー発見
        providers = self.discover_etw_providers()
        result.etw_providers = providers
        
        if not providers:
            print("Could not discover ETW providers")
            return result
        
        # 3. NPU/AI/GPU関連プロバイダー分析
        npu_providers, ai_providers, gpu_providers = self.find_npu_related_providers(providers)
        result.npu_related_providers = npu_providers
        result.ai_related_providers = ai_providers
        result.gpu_providers = gpu_providers
        
        # 4. ETWトレース実行（短時間デモ）
        print(f"\nWould you like to run a 15-second ETW trace for NPU activity? (y/n): ", end='')
        
        # 自動で'y'を選択（デモンストレーション用）
        print("y")
        choice = 'y'
        
        if choice.lower() == 'y':
            if self.run_npu_trace(duration=15):
                trace_analysis = self.analyze_trace_for_npu_activity()
                result.trace_results = trace_analysis
        
        return result
    
    def generate_wpt_recommendations(self, result: WPTResult) -> List[str]:
        """WPT使用推奨事項を生成"""
        recommendations = []
        
        if not result.tool_available:
            recommendations.extend([
                "Install Windows Assessment and Deployment Kit (ADK)",
                "Or install Windows SDK with Windows Performance Toolkit",
                "Download from: https://docs.microsoft.com/en-us/windows-hardware/get-started/adk-install"
            ])
            return recommendations
        
        if result.npu_related_providers:
            recommendations.extend([
                f"Found {len(result.npu_related_providers)} NPU-related ETW providers:",
                *[f"  - {provider}" for provider in result.npu_related_providers],
                "Use these providers for detailed NPU monitoring"
            ])
        
        if result.ai_related_providers:
            recommendations.extend([
                f"Found {len(result.ai_related_providers)} AI-related ETW providers:",
                *[f"  - {provider}" for provider in result.ai_related_providers[:3]],
                "Monitor these for AI framework activity"
            ])
        
        if result.gpu_providers:
            recommendations.extend([
                f"Found {len(result.gpu_providers)} GPU-related ETW providers",
                "GPU providers may include NPU activity for integrated NPUs"
            ])
        
        if result.trace_results:
            recommendations.extend([
                "ETW trace completed successfully",
                f"Trace file: {result.trace_results.get('trace_file', 'unknown')}",
                "Use WPA for detailed analysis:",
                f"  wpa.exe {result.trace_results.get('trace_file', 'npu_trace.etl')}"
            ])
        
        # 一般的な推奨事項
        recommendations.extend([
            "",
            "Advanced NPU monitoring with WPT:",
            "1. Create custom ETW providers for NPU drivers",
            "2. Use GPU scheduler events to detect compute workloads",
            "3. Monitor DirectML provider for AI inference activity",
            "4. Correlate power events with AI workload patterns",
            "5. Track process creation for AI frameworks"
        ])
        
        return recommendations

def main():
    """メイン関数"""
    print("Windows Performance Toolkit NPU Investigation")
    print("Exploring ETW providers and tracing for NPU activity detection")
    print()
    
    investigator = WPTNPUInvestigator()
    
    # 包括的調査実行
    result = investigator.comprehensive_wpt_investigation()
    
    # 推奨事項生成
    recommendations = investigator.generate_wpt_recommendations(result)
    
    # 結果表示
    print(f"\n{'='*80}")
    print(" WPT INVESTIGATION RESULTS")
    print(f"{'='*80}")
    
    print(f"WPT Available: {'✓' if result.tool_available else '✗'}")
    print(f"ETW Providers Found: {len(result.etw_providers)}")
    print(f"NPU-related Providers: {len(result.npu_related_providers)}")
    print(f"AI-related Providers: {len(result.ai_related_providers)}")
    print(f"GPU-related Providers: {len(result.gpu_providers)}")
    print(f"ETW Trace Completed: {'✓' if result.trace_results else '✗'}")
    
    print(f"\n{'='*60}")
    print(" RECOMMENDATIONS")
    print(f"{'='*60}")
    
    for recommendation in recommendations:
        print(recommendation)
    
    # クリーンアップ
    try:
        if os.path.exists("npu_monitor_profile.wprp"):
            os.remove("npu_monitor_profile.wprp")
        if os.path.exists("npu_trace.etl"):
            print(f"\nNote: Trace file 'npu_trace.etl' kept for analysis")
    except:
        pass

if __name__ == "__main__":
    main()