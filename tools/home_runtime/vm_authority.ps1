$ErrorActionPreference='Stop'
if($env:COMPUTERNAME -ne 'LAPTOP-NPSGA016'){throw 'wrong host'}
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class AnalystHomeScm {
  [DllImport("advapi32.dll", EntryPoint="OpenSCManagerW", ExactSpelling=true, SetLastError=true)]
  private static extern IntPtr Open(IntPtr machine, IntPtr database, uint mask);
  [DllImport("advapi32.dll", SetLastError=true)] private static extern bool CloseServiceHandle(IntPtr h);
  public static int CanCreate() {
    var h=Open(IntPtr.Zero, IntPtr.Zero, 2);
    if(h==IntPtr.Zero) return Marshal.GetLastWin32Error();
    CloseServiceHandle(h); return 0;
  }
}
'@
$info=[ordered]@{scm_create_error=[AnalystHomeScm]::CanCreate();vmms='not_visible';provider='unknown';module='absent';vm='unattempted';default_switch=$null}
$service=Get-Service -Name vmms -ErrorAction SilentlyContinue
if($service){$info.vmms=[string]$service.Status}
try {
    $rows=@(Get-CimInstance -Namespace 'root\virtualization\v2' -ClassName Msvm_VirtualSystemManagementService -ErrorAction Stop)
    $info.provider=$(if($rows.Count){'readable'}else{'no_management_instance'})
} catch { $info.provider=('0x{0:X8}' -f $_.Exception.HResult) }
try { Import-Module Hyper-V -ErrorAction Stop; $info.module='available' } catch {}
if($info.module -eq 'available'){
    try {
        $null=Get-VMHost -ErrorAction Stop
        $vmName='AnalystAI-Home-Production'
        $marker='AnalystAI owner runtime home v1'
        $known=@(Get-VM -ErrorAction Stop | Where-Object Name -ceq $vmName)
        if($known.Count){
            $info.vm=$(if($known.Count -eq 1 -and $known[0].Notes -ceq $marker){'owned_vm_present'}else{'name_occupied'})
        } else {
            $vm=New-VM -Name $vmName -NoVHD -Generation 2 -MemoryStartupBytes 2GB -ErrorAction Stop
            try {
                Set-VM -VM $vm -Notes $marker -AutomaticStartAction Nothing -ErrorAction Stop
                $actual=Get-VM -Id $vm.Id -ErrorAction Stop
                if($actual.State -ne 'Off' -or $actual.Notes -cne $marker -or $actual.Generation -ne 2){throw 'vm verification failed'}
                $info.vm='owned_empty_vm_created'
            } catch {
                $ours=Get-VM -Id $vm.Id -ErrorAction Stop
                if($ours.State -eq 'Off' -and $ours.Name -ceq $vmName -and @(Get-VMHardDiskDrive -VM $ours).Count -eq 0){Remove-VM -VM $ours -Force -ErrorAction Stop}
                throw
            }
        }
        $info.default_switch=[bool](@(Get-VMSwitch -ErrorAction Stop | Where-Object Name -ceq 'Default Switch').Count)
    } catch {
        $info.vm=('provider_or_create_error_0x{0:X8}' -f $_.Exception.HResult)
        $info.error_identifier=(($_.FullyQualifiedErrorId -split ',')[0] -replace '[^A-Za-z0-9._+-]','').Substring(0,[Math]::Min(80,(($_.FullyQualifiedErrorId -split ',')[0] -replace '[^A-Za-z0-9._+-]','').Length))
    }
}
$info|ConvertTo-Json -Compress
