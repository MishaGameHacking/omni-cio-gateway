"use strict";

/* Public interface configuration shared by the page and its service worker.
   Durations use milliseconds unless a property explicitly names another unit.
   These are presentation/request budgets, never server authorization or trading
   limits. Financial policy and the application version remain server-owned. */
(() => {
  const config = {
    compiledBuild: "__OMNICIO_BUILD__",
    units: {millisecondsPerSecond: 1000, secondsPerDay: 86400, millisecondsPerDay: 86400000},
    timing: {
      requestMs: 30000,
      portfolioRequestMs: 45000,
      calculationRequestMs: 60000,
      proposalRequestMs: 65000,
      assistantRequestMs: 120000,
      researchRequestMs: 305000,
      refreshPollMs: 2500,
      refreshRetryMaxMs: 60000,
      freshnessPaintMs: 60000,
      quotePollMs: 10000,
      quoteOfflineRetryMs: 15000,
      eventSummaryPollMs: 30000,
      eventSummaryChangedMs: 100,
      autosaveDebounceMs: 600,
      toastMs: 4200,
      errorToastMs: 7000,
      quoteReconnectBaseMs: 1000,
      quoteReconnectMaxMs: 30000,
      quoteReconnectExponentMax: 5,
      assessmentClockSkewMs: 5000,
      // Browsers store timer delays as signed 32-bit integers.
      timerMaxMs: 2147483647,
      downloadUrlLifetimeMs: 1000,
      researchReadbackMs: 120000,
      updateDraftLifetimeMs: 1800000,
      workerReadyMs: 15000,
      workerMessageMs: 5000,
      workerStorageMs: 1000,
      publicCacheRepairMs: 30000,
      notificationClientAckMs: 1500
    },
    limits: {
      searchQueryCharacters: 64,
      routeValueCharacters: 256,
      identifierCharacters: 128,
      conversationTitleCharacters: 120,
      assistantReplyCharacters: 100000,
      assistantStreamBufferCharacters: 524288,
      updateDraftFieldCharacters: 12000,
      updateDraftBytes: 131072,
      researchEvidenceBytes: 16 * 1024 * 1024,
      emailCharacters: 254,
      displayNameCharacters: 80
    },
    pagination: {
      // Keep quote batches bounded even when the table contains many positions.
      quoteBatchSize: 50,
      pageSize: 50,
      researchChoicesPageSize: 200,
      historyObservations: 365,
      compactAssets: 5,
      compactEvents: 4,
      publicNews: 8,
      compactGoals: 2,
      assetPayouts: 12
    },
    // Early form feedback mirrors the API contract. The server independently
    // validates all amounts and limits; changing this group grants no authority.
    formLimits: {
      amountRubMax: 1000000000000,
      percentMax: 100,
      horizonMonthsMax: 1200,
      liquidityDaysMax: 36500,
      costBasisPointsMax: 1000,
      credentialCharactersMax: 4096,
      brokerCredentialCharactersMin: 20,
      assistantMessageCharactersMax: 4000,
      assistantMemoryCharactersMax: 1000
    },
    display: {
      timeZone: "Europe/Moscow",
      locales: {ru: "ru-RU", en: "en-US"},
      numberFractionDigits: 2,
      marketPriceFractionDigits: 9,
      chartAxisFractionDigitsMax: 20,
      periodDays: {"1d": 1, "1w": 7, "1m": 31, "3m": 93, "1y": 365}
    },
    charts: {
      width: 480,
      height: 180,
      edgeInset: 1,
      compactTop: 12,
      compactBottom: 173,
      flatRangeRatio: .005,
      rangePaddingRatio: .1,
      gridFractions: [0, .5, 1],
      comparisonColorCount: 2,
      allocationColorCount: 6,
      donutSize: 120,
      donutCenter: 60,
      donutRadius: 47
    }
  };
  // Freeze nested groups too: a consumer cannot alter another view's settings.
  const freeze = value => {
    if (value && typeof value === "object") {
      for (const child of Object.values(value)) freeze(child);
      Object.freeze(value);
    }
    return value;
  };
  const api = freeze(config);
  globalThis.OMNICIO_CONFIG = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
