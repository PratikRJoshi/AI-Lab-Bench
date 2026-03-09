package com.example.bogleheads.parser;

import com.example.bogleheads.mcp.model.ContextChunk;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.select.Elements;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Parser responsible for turning raw html thread pages into {@link ContextChunk}s.
 */
@Service
public class ParserService {

    private static final Pattern THREAD_ID_PATTERN = Pattern.compile("viewtopic\\.php\\?t=([0-9]+)");
    private static final Pattern POST_ID_PATTERN = Pattern.compile("p=([0-9]+)");

    /**
     * Parse a single raw HTML file (downloaded thread page) into one or more chunks.
     * @param htmlPath path to html file
     * @return list of ContextChunk objects
     * @throws IOException on IO error
     */
    public List<ContextChunk> parse(Path htmlPath) throws IOException {
        List<ContextChunk> chunks = new ArrayList<>();
        Document doc = Jsoup.parse(htmlPath.toFile(), StandardCharsets.UTF_8.name());

        // Determine thread id from title anchor href inside the first topictitle link, fallback to file name
        String threadId = guessThreadId(doc, htmlPath.getFileName().toString());

        // Each post is in <div id="pXXXX" class="post">
        Elements postDivs = doc.select("div.post");
        for (Element postDiv : postDivs) {
            String postId = postDiv.id().replaceFirst("^p", "");
            // Author timestamp sometimes under <p class="author">
            Element content = postDiv.selectFirst("div.postbody");
            if (content == null) continue;
            String text = content.text();
            String url = "https://www.bogleheads.org/forum/viewtopic.php?t=" + threadId + "#p" + postId;
            String id = threadId + "#" + postId;
            chunks.add(new ContextChunk(id, text, url));
        }
        return chunks;
    }

    private String guessThreadId(Document doc, String fallback) {
        Element topicLink = doc.selectFirst("a.topictitle");
        if (topicLink != null) {
            Matcher m = THREAD_ID_PATTERN.matcher(topicLink.attr("href"));
            if (m.find()) return m.group(1);
        }
        Matcher m2 = THREAD_ID_PATTERN.matcher(fallback);
        return m2.find() ? m2.group(1) : fallback.replace(".html", "");
    }

    /**
     * Utility that scans a directory tree for .html files and parses them.
     */
    public List<ContextChunk> parseDirectory(Path dir) throws IOException {
        List<ContextChunk> out = new ArrayList<>();
        Files.walk(dir)
             .filter(p -> p.toString().endsWith(".html"))
             .forEach(path -> {
                 try {
                     out.addAll(parse(path));
                 } catch (IOException e) {
                     throw new RuntimeException(e);
                 }
             });
        return out;
    }
}
