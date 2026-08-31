export default {
  async fetch() {
    return new Response(
      JSON.stringify({ detail: "CLOUDFLARE_PRODUCTION_BOOTSTRAP_PENDING" }),
      {
        status: 503,
        headers: {
          "cache-control": "no-store",
          "content-type": "application/json; charset=utf-8",
          "x-content-type-options": "nosniff",
        },
      },
    );
  },
};
