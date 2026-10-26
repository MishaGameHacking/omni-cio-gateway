"""Administrative source-text delta; apply and verify only on the Windows host.

Prepared separately so the already verified APK can complete native acceptance.
"""


def apply(files, base):
    path = 'app/src/main/java/ru/omnicio/app/ui/portfolio/PortfolioAssetBrowser.kt'
    value = files[path] if path in files else base(path)
    old = '''    val lookup = candidates.associateBy(::portfolioRowKey)
    val candidateKeys = candidates.map(::portfolioRowKey)
    val stableKeys = frozenOrder?.filter { it in lookup }?.let { it + candidateKeys.filterNot(it::contains) } ?: candidateKeys
    val rows = stableKeys.mapNotNull(lookup::get)
    LaunchedEffect(candidateKeys) { if (frozenOrder == null) frozenOrder = candidateKeys }
    val restricted = rows.filter { it.position.blocked }
    val cash = rows.filter { it.position.instrumentType in setOf("cash", "currency") && !it.position.blocked }
    val assets = rows.filter { !it.position.blocked && it.position.instrumentType !in setOf("cash", "currency") }
    val groups = assets.groupBy { portfolioGroupLabel(it, group, exposureAxis) }'''
    new = '''    val lookup = remember(candidates) { candidates.associateBy(::portfolioRowKey) }
    val candidateKeys = remember(candidates) { candidates.map(::portfolioRowKey) }
    val stableKeys = remember(frozenOrder, candidateKeys) { stablePortfolioRowKeys(frozenOrder, candidateKeys) }
    val rows = remember(stableKeys, lookup) { stableKeys.mapNotNull(lookup::get) }
    LaunchedEffect(candidateKeys) { if (frozenOrder == null) frozenOrder = candidateKeys }
    val restricted = remember(rows) { rows.filter { it.position.blocked } }
    val cash = remember(rows) { rows.filter {
        (it.position.instrumentType == "cash" || it.position.instrumentType == "currency") && !it.position.blocked
    } }
    val assets = remember(rows) { rows.filter {
        !it.position.blocked && it.position.instrumentType != "cash" && it.position.instrumentType != "currency"
    } }
    val groups = remember(assets, group, exposureAxis) { assets.groupBy { portfolioGroupLabel(it, group, exposureAxis) } }'''
    assert value.count(old) == 1
    value = value.replace(old, new)
    anchor = 'internal fun portfolioRowKey(row: PortfolioRow): String = "${row.account.id}:${row.position.id}"'
    assert value.count(anchor) == 1
    value = value.replace(anchor, '''/** Keep visible order stable while appending fresh positions in current server order. */
internal fun stablePortfolioRowKeys(previous: List<String>?, current: List<String>): List<String> {
    if (previous == null) return current
    val available = current.toHashSet()
    val retained = previous.filter(available::contains)
    val known = retained.toHashSet()
    return retained + current.filterNot(known::contains)
}

''' + anchor)
    files[path] = value
    path = 'app/src/test/java/ru/omnicio/app/ui/portfolio/WorkspaceFinancialSemanticsTest.kt'
    value = files[path] if path in files else base(path)
    anchor = 'class WorkspaceFinancialSemanticsTest {'
    assert value.count(anchor) == 1
    value = value.replace(anchor, anchor + '''
    @Test fun refreshedPortfolioKeepsExistingRowsInPlaceAndAppendsNewPositions() {
        val original = listOf("account-a:bond", "account-b:share", "account-a:expired")
        val refreshed = listOf("account-b:new", "account-b:share", "account-a:bond", "account-a:new")
        assertEquals(listOf("account-a:bond", "account-b:share", "account-b:new", "account-a:new"),
            stablePortfolioRowKeys(original, refreshed))
        assertEquals(refreshed, stablePortfolioRowKeys(null, refreshed))
        assertEquals(refreshed, stablePortfolioRowKeys(emptyList(), refreshed))
        assertEquals(emptyList<String>(), stablePortfolioRowKeys(original, emptyList()))
        // Equal instrument IDs on different accounts are different positions.
        assertEquals(listOf("account-b:same", "account-a:same"),
            stablePortfolioRowKeys(listOf("account-b:same"), listOf("account-a:same", "account-b:same")))
    }
''')
    files[path] = value
