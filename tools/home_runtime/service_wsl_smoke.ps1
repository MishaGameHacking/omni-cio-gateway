param([Parameter(Mandatory)][string]$SourceFile)
$ErrorActionPreference='Stop'
if ($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016' -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -ne 'S-1-5-20') { throw 'Expected limited physical runner' }
$folder=Join-Path ([IO.Path]::GetTempPath()) ('analyst-wsl-host-'+[guid]::NewGuid().ToString('N'))
$bin=Join-Path $folder 'host'
$null=[IO.Directory]::CreateDirectory($bin)
try {
    $proof=@'
$ErrorActionPreference='Stop'
$wsl=Join-Path $env:SystemRoot 'System32\wsl.exe'
$p=[Diagnostics.Process]::new()
$p.StartInfo=[Diagnostics.ProcessStartInfo]::new($wsl,'-d AnalystAI-Home -u analyst-ai --exec /bin/sleep 150')
$p.StartInfo.UseShellExecute=$false;$p.StartInfo.CreateNoWindow=$true
$null=$p.Start()
$file=Join-Path $PSScriptRoot 'process.txt'
[IO.File]::WriteAllText($file+'.next',([string]$PID+' '+[string]$p.Id))
[IO.File]::Move($file+'.next',$file)
$p.WaitForExit()
'@
    $worker=Join-Path $folder 'Run-AnalystAIHome.ps1'
    [IO.File]::WriteAllText($worker,$proof)
    $hash=(Get-FileHash $worker -Algorithm SHA256).Hash.ToLowerInvariant()
    $source=[IO.File]::ReadAllText($SourceFile)
    if ((Get-FileHash $SourceFile -Algorithm SHA256).Hash -ne 'fc2e2f5dae51c82d7295c733bbd15884be089216092a30e9fb45fe317d655c7e') { throw 'Unreviewed host source' }
    $source=$source.Replace('__WORKER_DIGEST__',$hash)
    $harness=@'
namespace AnalystHome {
    public static class LinuxProof {
        static int Status(string route) {
            try {
                var req=System.Net.WebRequest.CreateHttp("http://127.0.0.1:18157"+route);
                req.Proxy=null; req.Timeout=2300;req.AllowAutoRedirect=false;
                using (var response=(System.Net.HttpWebResponse)req.GetResponse()) {
                    using (var reader=new System.IO.StreamReader(response.GetResponseStream())) {
                        string text=reader.ReadToEnd().Replace(" ","").Trim();
                        return route=="/health" && text!="{\"status\":\"ok\"}" ? 0 : (int)response.StatusCode;
                    }
                }
            } catch(System.Net.WebException e) {
                using(var res=e.Response as System.Net.HttpWebResponse) { return res==null?0:(int)res.StatusCode; }
            }
        }
        public static int Main() {
            var binding=System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Instance;
            var host=new ServiceHost();
            var start=typeof(ServiceHost).GetMethod("OnStart",binding);
            var stop=typeof(ServiceHost).GetMethod("OnStop",binding);
            var root=System.IO.Directory.GetParent(AppDomain.CurrentDomain.BaseDirectory.TrimEnd(System.IO.Path.DirectorySeparatorChar)).FullName;
            var marker=System.IO.Path.Combine(root,"process.txt");
            System.Diagnostics.Process worker=null,linux=null;
            try {
                start.Invoke(host,new object[]{new string[0]});
                try {
                    var end=DateTime.UtcNow.AddSeconds(65);
                    while(DateTime.UtcNow<end && (!System.IO.File.Exists(marker)||Status("/health")!=200)) System.Threading.Thread.Sleep(700);
                    var ids=System.IO.File.ReadAllText(marker).Split(' ');
                    worker=System.Diagnostics.Process.GetProcessById(int.Parse(ids[0]));
                    linux=System.Diagnostics.Process.GetProcessById(int.Parse(ids[1]));
                    if(worker.ProcessName.ToLowerInvariant()!="powershell"||linux.ProcessName.ToLowerInvariant()!="wsl")return 21;
                    for(int i=0;i<2;i++) {
                        if(Status("/health")!=200||Status("/me")!=401||worker.HasExited||linux.HasExited)return 22;
                        if(i==0)System.Threading.Thread.Sleep(15000);
                    }
                } finally { stop.Invoke(host,null); }
                if(!worker.WaitForExit(6000)||!linux.WaitForExit(6000))return 23;
                Console.WriteLine("HOME_WINDOWS_LINUX_ANCHOR={\"existing_ubuntu\":true,\"limited_windows_account\":true,\"health\":200,\"anonymous\":401,\"checks\":2,\"both_owned_processes_stopped\":true,\"service_installed_by_test\":false}");
                return 0;
            } catch(Exception e) {
                var x=e.GetBaseException();
                Console.WriteLine("HOME_ANCHOR_ERROR="+x.GetType().Name+":"+x.HResult.ToString("X8"));
                return 24;
            } finally { if(worker!=null) worker.Dispose(); if(linux!=null) linux.Dispose();host.Dispose(); }
        }
    }
}
'@
    $provider=[Microsoft.CSharp.CSharpCodeProvider]::new()
    $params=[CodeDom.Compiler.CompilerParameters]::new()
    $params.GenerateExecutable=$true;$params.OutputAssembly=Join-Path $bin 'linux-proof.exe'
    $params.CompilerOptions='/nologo /platform:x64 /main:AnalystHome.LinuxProof'
    $null=$params.ReferencedAssemblies.Add('System.dll')
    $null=$params.ReferencedAssemblies.Add('System.ServiceProcess.dll')
    try {
        $result=$provider.CompileAssemblyFromSource($params,($source+[Environment]::NewLine+$harness))
        if ($result.Errors.HasErrors) { throw ('QA compilation '+$result.Errors[0].ErrorNumber) }
    } finally { $provider.Dispose() }
    & $params.OutputAssembly
    if ($LASTEXITCODE) { throw ('Windows/Linux fixture exit '+$LASTEXITCODE) }
} finally { if ([IO.Directory]::Exists($folder)) { [IO.Directory]::Delete($folder,$true) } }
