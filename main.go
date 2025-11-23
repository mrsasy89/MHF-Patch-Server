package main

import (
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "flag"
    "fmt"
    "io"
    "io/fs"
    "log"
    "net/http"
    "os"
    "path/filepath"
    "strings"
)

var (
    config     Config
    folderData DirData
)

type Config struct {
    PatchPort   int    `json:"PatchPort"`
    ImagePort   int    `json:"ImagePort"`
    GameFolder  string `json:"GameFolder"`
    ImageFolder string `json:"ImageFolder"`
    Force       bool   `json:"Force"`
    MaxClients  int    `json:"MaxClients"`
}

type DirData struct {
    ChecksumHeader string
    ChecksumsBody  []byte
}

func loadConfig(path string) {
    data, err := os.ReadFile(path)
    if err != nil {
        log.Fatal(err)
    }
    if err := json.Unmarshal(data, &config); err != nil {
        log.Fatal(err)
    }
    config.GameFolder, err = filepath.Abs(config.GameFolder)
    if err != nil {
        log.Fatal(err)
    }
    config.ImageFolder, err = filepath.Abs(config.ImageFolder)
    if err != nil {
        log.Fatal(err)
    }
}

func loadFolderData() {
    var err error
    hasher := sha256.New()
    err = filepath.WalkDir(config.GameFolder, func(path string, d fs.DirEntry, err error) error {
        if err != nil {
            log.Fatal(err)
        }
        if d.IsDir() || strings.HasSuffix(path, ".gitkeep") {
            return nil
        }
        f, err := os.Open(path)
        if err != nil {
            log.Fatal(err)
        }
        defer f.Close()
        fileHasher := sha256.New()
        if _, err := io.Copy(fileHasher, f); err != nil {
            log.Fatal(err)
        }
        checksum := hex.EncodeToString(fileHasher.Sum(nil))
        rel := strings.ReplaceAll(strings.TrimPrefix(path, config.GameFolder), "\\", "/")
        line := []byte(fmt.Sprintf("%s\t%s\n", checksum, rel))
        folderData.ChecksumsBody = append(folderData.ChecksumsBody, line...)
        hasher.Write(line)
        return nil
    })
    if err != nil {
        log.Fatal(err)
    }
    folderData.ChecksumHeader = fmt.Sprintf("\"%s\"", hex.EncodeToString(hasher.Sum(nil)))
}

// concurrencyLimiter wraps a handler to limit concurrent requests
func concurrencyLimiter(max int, h http.Handler) http.Handler {
    sem := make(chan struct{}, max)
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        sem <- struct{}{}
        defer func() { <-sem }()
        h.ServeHTTP(w, r)
    })
}

func checkHandler(w http.ResponseWriter, r *http.Request) {
    etag := r.Header.Get("If-None-Match")
    if !config.Force && etag == folderData.ChecksumHeader {
        w.WriteHeader(http.StatusNotModified)
        return
    }
    w.Header().Set("ETag", folderData.ChecksumHeader)
    w.WriteHeader(http.StatusOK)
    w.Write(folderData.ChecksumsBody)
}

func main() {
    cfg := flag.String("config", "./patch_config.json", "path to config file")
    flag.Parse()

    loadConfig(*cfg)
    loadFolderData()

    // Patch server mux
    patchMux := http.NewServeMux()
    patchMux.HandleFunc("/check", checkHandler)
    patchMux.Handle("/", http.FileServer(http.Dir(config.GameFolder)))

    // Start patch server with concurrency limit
    go func() {
        addr := fmt.Sprintf(":%d", config.PatchPort)
        log.Printf("Starting patch server on %s (max %d clients)", addr, config.MaxClients)
        handler := concurrencyLimiter(config.MaxClients, patchMux)
        if err := http.ListenAndServe(addr, handler); err != nil {
            log.Fatal(err)
        }
    }()

    // Image server for hosting
    imgHandler := http.FileServer(http.Dir(config.ImageFolder))
    imgAddr := fmt.Sprintf(":%d", config.ImagePort)
    log.Printf("Starting image server on %s serving %s", imgAddr, config.ImageFolder)
    if err := http.ListenAndServe(imgAddr, imgHandler); err != nil {
        log.Fatal(err)
    }
}
