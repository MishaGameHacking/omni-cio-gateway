import com.android.apksig.ApkVerifier;
import com.android.apksig.apk.ApkFormatException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.GeneralSecurityException;
import java.security.cert.X509Certificate;
import java.util.HexFormat;
import java.util.List;
import java.util.Locale;

/** Machine-readable identity from verified APK bytes, never from CLI wording. */
final class VerifyApkSigning {
    private static final long MAX_APK_BYTES = 268_435_456L;

    private VerifyApkSigning() {}

    private static void require(boolean valid, String code) {
        if (!valid) throw new SecurityException(code);
    }

    private static String sha256(Path apk) throws IOException, GeneralSecurityException {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        long total = 0;
        byte[] buffer = new byte[65_536];
        try (InputStream input = Files.newInputStream(apk)) {
            int count;
            while ((count = input.read(buffer)) != -1) {
                total += count;
                require(total <= MAX_APK_BYTES, "apk_size_limit");
                digest.update(buffer, 0, count);
            }
        }
        require(total > 0, "empty_apk");
        return HexFormat.of().formatHex(digest.digest());
    }

    private static void certificate(X509Certificate certificate, String expected) throws GeneralSecurityException {
        require(certificate != null, "missing_certificate");
        String observed = HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(certificate.getEncoded()));
        require(observed.equals(expected), "certificate_not_pinned;observed_sha256=" + observed);
    }

    private static void identity(ApkVerifier.Result result, String expected) throws GeneralSecurityException {
        require(result.isVerified(), "signature_not_verified");
        List<X509Certificate> signers = result.getSignerCertificates();
        require(signers.size() == 1, "expected_single_signer");
        certificate(signers.get(0), expected);
        // Do not let a matching active signer authorize another SDK-targeted key.
        for (var signer : result.getV1SchemeSigners()) certificate(signer.getCertificate(), expected);
        for (var signer : result.getV2SchemeSigners()) certificate(signer.getCertificate(), expected);
        for (var signer : result.getV3SchemeSigners()) certificate(signer.getCertificate(), expected);
        for (var signer : result.getV31SchemeSigners()) certificate(signer.getCertificate(), expected);
        var lineage = result.getSigningCertificateLineage();
        if (lineage != null) {
            for (var signer : lineage.getCertificatesInLineage()) certificate(signer, expected);
        }
    }

    private static void verify(String[] args) throws IOException, GeneralSecurityException, ApkFormatException {
        require(args.length == 2, "expected_apk_and_certificate_pin");
        Path apk = Path.of(args[0]);
        String expected = args[1];
        require(expected.matches("[0-9a-f]{64}"), "invalid_certificate_pin");
        require(Files.isRegularFile(apk, LinkOption.NOFOLLOW_LINKS), "invalid_apk_file");
        long bytes = Files.size(apk);
        require(bytes > 0 && bytes <= MAX_APK_BYTES, "apk_size_limit");
        String before = sha256(apk);
        // Same official library shipped in pinned Android Build Tools 37.0.0.
        ApkVerifier.Result result = new ApkVerifier.Builder(apk.toFile())
                .setMinCheckedPlatformVersion(37).build().verify();
        identity(result, expected);
        // V3 verification can intentionally skip the V2 block on current Android.
        // Inspect that format independently, NOT an installation/OS-support test.
        // The signature-format interval is defined by apksig's public contract.
        ApkVerifier.Result v2 = new ApkVerifier.Builder(apk.toFile())
                .setMinCheckedPlatformVersion(24).setMaxCheckedPlatformVersion(27).build().verify();
        identity(v2, expected);
        require(v2.isVerifiedUsingV2Scheme(), "v2_signature_not_verified");
        require(Files.size(apk) == bytes && sha256(apk).equals(before), "apk_changed_during_verification");
        System.out.printf(Locale.ROOT,
                "{\"schema\":1,\"tool\":\"android-apksig\",\"android_api\":37,"
                + "\"apk_sha256\":\"%s\",\"bytes\":%d,\"certificate_sha256\":\"%s\","
                + "\"signers\":1,\"signature_v2\":true}%n", before, bytes, expected);
    }

    public static void main(String[] args) {
        try {
            verify(args);
        } catch (SecurityException rejected) {
            // Fixed diagnostics and PUBLIC certificate hashes only, never key material or DNs.
            System.err.println("APK_SIGNATURE_FAILURE=" + rejected.getMessage());
            System.exit(1);
        } catch (IOException | GeneralSecurityException | ApkFormatException | IllegalArgumentException | IllegalStateException failure) {
            System.err.println("APK_SIGNATURE_FAILURE=" + failure.getClass().getSimpleName());
            System.exit(1);
        }
    }
}
