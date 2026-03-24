package com.example.bogleheads.scraper;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Service responsible for discovering forum thread URLs from the bogleheads.org index pages.
 * <p>
 * NOTE: This is an initial implementation meant for a small proof-of-concept crawl.  In production
 * you should add polite crawling practices (rate-limiting, retry-with-backoff, user-agent header,
 * distributed queue, etc.) and unit tests that stub HTTP calls.
 */
@Service
public class ScraperService {

    private static final String INDEX_URL = "https://www.bogleheads.org/forum/index.php";
    private static final String BASE_URL = "https://www.bogleheads.org/forum/";
    private static final int TIMEOUT_MS = (int) Duration.ofSeconds(30).toMillis();
    private static final Pattern THREAD_ID_PATTERN = Pattern.compile("viewtopic\\.php\\?t=([0-9]+)");

    // Realistic browser User-Agent to avoid bot detection
    private static final String USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";

    // Cookie jar for session persistence across requests
    private final Map<String, String> cookies = new java.util.HashMap<>();

    public ScraperService(@Value("${app.scraper.cf-clearance-cookie:}") String cfClearanceCookie) {
        // If CloudFlare clearance cookie is provided, pre-populate the cookie jar
        if (cfClearanceCookie != null && !cfClearanceCookie.trim().isEmpty()) {
            cookies.put("cf_clearance", cfClearanceCookie.trim());
        }
    }

    /**
     * Build a Jsoup connection with browser-like headers and cookie persistence.
     *
     * @param url     The URL to connect to
     * @param referer The Referer header value (null if none)
     * @return A configured Jsoup Connection
     */
    private org.jsoup.Connection buildConnection(String url, String referer) {
        org.jsoup.Connection conn = Jsoup.connect(url)
                .userAgent(USER_AGENT)
                .timeout(TIMEOUT_MS)
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                .header("Accept-Language", "en-US,en;q=0.5")
                .header("Accept-Encoding", "gzip, deflate")
                .header("Connection", "keep-alive")
                .cookies(cookies);

        if (referer != null) {
            conn.header("Referer", referer);
        }

        return conn;
    }

    /**
     * Crawl the forum index and return discovered thread URLs.
     *
     * @param topicPagesPerForum How many topic pages to crawl per forum (100 topics per page).
     * @return List of absolute thread URLs.
     * @throws IOException if network or parsing fails.
     */
    public List<String> crawlIndex(int topicPagesPerForum) throws IOException, InterruptedException {
        List<String> threads = new ArrayList<>();

        // Step 1: fetch the main index and collect forum links
        org.jsoup.Connection.Response indexResponse = buildConnection(INDEX_URL, null).execute();
        cookies.putAll(indexResponse.cookies());
        Document indexDoc = indexResponse.parse();
        List<String> forumUrls = extractForumUrls(indexDoc);

        // Step 2: iterate through each forum and collect topic links
        for (String forumUrl : forumUrls) {
            for (int page = 0; page < topicPagesPerForum; page++) {
                String pagedUrl = forumUrl + "&start=" + (page * 100);
                org.jsoup.Connection.Response forumResponse = buildConnection(pagedUrl, INDEX_URL).execute();
                cookies.putAll(forumResponse.cookies());
                Document forumDoc = forumResponse.parse();
                threads.addAll(extractThreadUrls(forumDoc));

                // Rate limiting between forum page fetches
                if (page < topicPagesPerForum - 1) {
                    Thread.sleep(2000);
                }
            }
            // Pause between forums
            Thread.sleep(2000);
        }
        return threads;
    }

    private List<String> extractThreadUrls(Document doc) {
        return doc.select("a.topictitle")
                  .stream()
                  .map(el -> el.attr("href"))
                  .map(href -> href.startsWith("./") ? href.substring(2) : href)
                  .filter(href -> href.startsWith("viewtopic.php?t="))
                  .map(href -> BASE_URL + href)
                  .distinct()
                  .toList();
    }

    private List<String> extractForumUrls(Document doc) {
        return doc.select("a.forumtitle")
                  .stream()
                  .map(el -> el.attr("href"))
                  .map(href -> href.startsWith("./") ? href.substring(2) : href) // strip leading ./
                  .filter(href -> href.startsWith("viewforum.php?f=")) // keep only forum pages
                  .map(href -> BASE_URL + href)
                  .distinct()
                  .toList();
    }

    /**
     * Download each thread URL and persist raw HTML under data/raw/YYYY/MM/DD/{threadId}.html
     * Performs a polite pause between requests.
     *
     * @param threadUrls List of thread URLs collected from {@link #crawlIndex(int)}
     * @param pauseMs    milliseconds to wait between HTTP requests
     */
    public void downloadThreads(List<String> threadUrls, long pauseMs) throws IOException, InterruptedException {
        LocalDate today = LocalDate.now();
        Path dayDir = Paths.get("data", "raw", today.format(DateTimeFormatter.ofPattern("yyyy/MM/dd")));
        Files.createDirectories(dayDir);

        for (String url : threadUrls) {
            String threadId = extractThreadId(url);
            if (threadId == null) continue; // skip unexpected url pattern

            Path outFile = dayDir.resolve(threadId + ".html");
            if (Files.exists(outFile)) continue; // already downloaded

            org.jsoup.Connection.Response response = buildConnection(url, BASE_URL + "index.php").execute();
            cookies.putAll(response.cookies());
            Document doc = response.parse();
            Files.writeString(outFile, doc.outerHtml(), StandardCharsets.UTF_8);
            Thread.sleep(pauseMs);
        }
    }

    private String extractThreadId(String url) {
        Matcher m = THREAD_ID_PATTERN.matcher(url);
        return m.find() ? m.group(1) : null;
    }
}
