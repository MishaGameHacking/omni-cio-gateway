export default {
  async fetch() {
    return new Response(
      JSON.stringify({
        status: "bootstrap",
        detail: "CLOUDFLARE_STAGING_BUILD_PENDING",
      }),
      {
        status: 503,
        headers: {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "no-store",
          "x-content-type-options": "nosniff",
        },
      },
    );
  },
};
