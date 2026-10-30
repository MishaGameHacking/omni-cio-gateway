using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.ServiceProcess;
using System.Threading;

namespace AnalystHome {
    public sealed class ServiceHost : ServiceBase {
        public const string NameInScm = "AnalystAIHomeHost";
        const string WorkerDigest = "__WORKER_DIGEST__";
        readonly object sync = new object();
        Process worker;
        IntPtr job;
        bool stopping;

        public ServiceHost() { ServiceName=NameInScm; CanShutdown=true; AutoLog=false; }
        public static void Main() { ServiceBase.Run(new ServiceHost()); }

        [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
            public long ProcessTime, JobTime;
            public uint LimitFlags;
            public UIntPtr MinWorkingSet, MaxWorkingSet;
            public uint ActiveProcesses;
            public UIntPtr Affinity;
            public uint Priority, Scheduling;
        }
        [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
            public BasicLimits Basic;
            public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
            public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
        }
        [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attrs, string name);
        [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr h, int kind, ref ExtendedLimits data, uint size);
        [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr h, IntPtr process);
        [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr h);

        protected override void OnStart(string[] args) {
            lock(sync) {
                using (var id=WindowsIdentity.GetCurrent()) {
                    if (id.IsSystem || new WindowsPrincipal(id).IsInRole(WindowsBuiltInRole.Administrator))
                        throw new InvalidOperationException("Limited service identity required.");
                }
                var directory=Directory.GetParent(AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar)).FullName;
                var path=Path.Combine(directory,"Run-AnalystAIHome.ps1");
                using (var sha=SHA256.Create())
                using (var file=File.OpenRead(path)) {
                    var actual=BitConverter.ToString(sha.ComputeHash(file)).Replace("-","");
                    if (!String.Equals(actual,WorkerDigest,StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Worker hash mismatch.");
                }
                job=CreateJobObject(IntPtr.Zero,null);
                if (job==IntPtr.Zero) throw new Win32Exception();
                try {
                    var limits=new ExtendedLimits();
                    limits.Basic.LimitFlags=0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    if (!SetInformationJobObject(job,9,ref limits,(uint)Marshal.SizeOf(typeof(ExtendedLimits)))) throw new Win32Exception();
                    var exe=Path.Combine(Environment.SystemDirectory,@"WindowsPowerShell\v1.0\powershell.exe");
                    var info=new ProcessStartInfo(exe,"-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \""+path+"\"");
                    info.UseShellExecute=false; info.CreateNoWindow=true; info.WorkingDirectory=directory;
                    worker=Process.Start(info);
                    if (!AssignProcessToJobObject(job,worker.Handle)) throw new Win32Exception();
                    worker.EnableRaisingEvents=true;
                    worker.Exited+=WorkerExited;
                    if (worker.HasExited) throw new InvalidOperationException("Worker exited before startup.");
                } catch {
                    if (worker!=null) { try { worker.Kill(); } catch (InvalidOperationException) {} }
                    CloseHandle(job); job=IntPtr.Zero;
                    throw;
                }
            }
        }
        void WorkerExited(object sender, EventArgs args) {
            lock(sync) { if (!stopping) Environment.Exit(1067); } // let SCM apply the configured restart delay
        }
        protected override void OnStop() {
            lock(sync) {
                stopping=true;
                if (job!=IntPtr.Zero) { CloseHandle(job); job=IntPtr.Zero; }
                if (worker!=null) { worker.Exited-=WorkerExited; worker.WaitForExit(8000); worker.Dispose(); worker=null; }
            }
        }
        protected override void OnShutdown() { OnStop(); }
    }

    public static class LogonRight {
        [StructLayout(LayoutKind.Sequential)] struct Attributes {
            public uint Length; public IntPtr Root, Name; public uint Flags; public IntPtr Security, Quality;
        }
        [StructLayout(LayoutKind.Sequential)] struct LsaString { public ushort Length, Maximum; public IntPtr Buffer; }
        [DllImport("advapi32.dll")] static extern uint LsaOpenPolicy(IntPtr system, ref Attributes attrs, uint access, out IntPtr handle);
        [DllImport("advapi32.dll")] static extern uint LsaAddAccountRights(IntPtr handle, byte[] sid, ref LsaString right, uint count);
        [DllImport("advapi32.dll")] static extern uint LsaNtStatusToWinError(uint status);
        [DllImport("advapi32.dll")] static extern uint LsaClose(IntPtr handle);
        static void Check(uint status) { if (status!=0) throw new Win32Exception((int)LsaNtStatusToWinError(status)); }
        public static void GrantServiceLogon(SecurityIdentifier sid) {
            var bytes=new byte[sid.BinaryLength]; sid.GetBinaryForm(bytes,0);
            var attrs=new Attributes(); attrs.Length=(uint)Marshal.SizeOf(typeof(Attributes));
            IntPtr handle; Check(LsaOpenPolicy(IntPtr.Zero,ref attrs,0x810,out handle));
            try {
                const string name="SeServiceLogonRight";
                var value=new LsaString(); value.Buffer=Marshal.StringToHGlobalUni(name);
                try { value.Length=(ushort)(name.Length*2); value.Maximum=(ushort)(value.Length+2); Check(LsaAddAccountRights(handle,bytes,ref value,1)); }
                finally { Marshal.FreeHGlobal(value.Buffer); }
            } finally { LsaClose(handle); }
        }
    }
}
