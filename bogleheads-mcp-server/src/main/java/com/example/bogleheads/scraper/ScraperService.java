package com.example.bogleheads.scraper;

import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
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

    /**
     * Crawl the forum index and return discovered thread URLs.
     *
     * @param topicPagesPerForum How many topic pages to crawl per forum (100 topics per page).
     * @return List of absolute thread URLs.
     * @throws IOException if network or parsing fails.
     */
    public List<String> crawlIndex(int topicPagesPerForum) throws IOException {
        List<String> threads = new ArrayList<>();

        // Step 1: fetch the main index and collect forum links
        Document indexDoc = Jsoup.connect(INDEX_URL)
                                 .userAgent("Mozilla/5.0 (compatible; bogleheads-mcp/1.0; +https://github.com/your-repo)")
                                 .timeout(TIMEOUT_MS)
                                 .get();
        List<String> forumUrls = extractForumUrls(indexDoc);

        // Step 2: iterate through each forum and collect topic links
        for (String forumUrl : forumUrls) {
            for (int page = 0; page < topicPagesPerForum; page++) {
                String pagedUrl = forumUrl + "&start=" + (page * 100);
                Document forumDoc = Jsoup.connect(pagedUrl)
                                          .userAgent("Mozilla/5.0 (compatible; bogleheads-mcp/1.0; +https://github.com/your-repo)")
                                          .timeout(TIMEOUT_MS)
                                          .get();
                threads.addAll(extractThreadUrls(forumDoc));
            }
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

            Document doc = Jsoup.connect(url)
                                .userAgent("Mozilla/5.0 (compatible; bogleheads-mcp/1.0; +https://github.com/your-repo)")
                                .timeout(TIMEOUT_MS)
                                .get();
            Files.writeString(outFile, doc.outerHtml(), StandardCharsets.UTF_8);
            Thread.sleep(pauseMs);
        }
    }

    private String extractThreadId(String url) {
        Matcher m = THREAD_ID_PATTERN.matcher(url);
        return m.find() ? m.group(1) : null;
    }
}
