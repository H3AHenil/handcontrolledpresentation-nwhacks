#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <cstring>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <chrono> // For timestamps

#include <opencv2/opencv.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/videoio.hpp>

// ================= Switches and Configurations =================
// 👇【Control Switch】Uncomment to enable latency probe, comment to disable
#define ENABLE_LATENCY_PROBE

#define DEFAULT_PORT 9999
#define WIDTH 1640       // 1640x1232 Full wide-angle resolution
#define HEIGHT 1232
#define FRAMERATE 30     // Recommended 30fps for high resolution
#define MAX_PACKET_SIZE 60000
#define JPEG_QUALITY 60  // Balance between quality and latency
// ===============================================================

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "❌ Usage: ./sender_probe <Target IP> [Port]" << std::endl;
        return -1;
    }

    std::string target_ip = argv[1];
    int target_port = (argc >= 3) ? std::stoi(argv[2]) : DEFAULT_PORT;

    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) return -1;

    int send_buf_size = 4 * 1024 * 1024;
    setsockopt(sock, SOL_SOCKET, SO_SNDBUF, &send_buf_size, sizeof(send_buf_size));

    struct sockaddr_in servaddr;
    std::memset(&servaddr, 0, sizeof(servaddr));
    servaddr.sin_family = AF_INET;
    servaddr.sin_port = htons(target_port);
    inet_pton(AF_INET, target_ip.c_str(), &servaddr.sin_addr);

    // 📷 GStreamer pipeline: 1640x1232, BGR (Color)
    std::string pipeline = "libcamerasrc ! video/x-raw, width=" + std::to_string(WIDTH) +
                           ", height=" + std::to_string(HEIGHT) + ", framerate=" + std::to_string(FRAMERATE) +
                           "/1 ! videoconvert ! video/x-raw, format=BGR ! "
                           "appsink drop=1 max-buffers=1 sync=false";

    std::cout << "📷 Starting camera: " << WIDTH << "x" << HEIGHT << " (Color/BGR)..." << std::endl;
    #ifdef ENABLE_LATENCY_PROBE
    std::cout << "⏱️  Latency Probe: [Enabled] (8-byte timestamp added to header)" << std::endl;
    #else
    std::cout << "⏱️  Latency Probe: [Disabled]" << std::endl;
    #endif

    cv::VideoCapture cap(pipeline, cv::CAP_GSTREAMER);
    if (!cap.isOpened()) {
        std::cerr << "❌ Unable to open camera" << std::endl;
        return -1;
    }

    cv::Mat frame;
    std::vector<unsigned char> encoded;
    std::vector<int> compression_params;
    compression_params.push_back(cv::IMWRITE_JPEG_QUALITY);
    compression_params.push_back(JPEG_QUALITY);

    uint8_t frame_id = 0;

    while (true) {
        cap.read(frame);
        if (frame.empty()) { usleep(1000); continue; }

        // Encode JPEG
        cv::imencode(".jpg", frame, encoded, compression_params);

        size_t total_size = encoded.size();
        int num_packets = std::ceil((double)total_size / MAX_PACKET_SIZE);

        // Prepare probe timestamp
        double timestamp = 0.0;
        #ifdef ENABLE_LATENCY_PROBE
            // Get current timestamp (seconds, double precision)
            auto now = std::chrono::system_clock::now();
            auto duration = now.time_since_epoch();
            timestamp = std::chrono::duration_cast<std::chrono::duration<double>>(duration).count();
        #endif

        for (int i = 0; i < num_packets; ++i) {
            size_t start_idx = i * MAX_PACKET_SIZE;
            size_t end_idx = std::min(start_idx + MAX_PACKET_SIZE, total_size);

            std::vector<uint8_t> packet;
            packet.reserve(MAX_PACKET_SIZE + 20);

            // === Protocol Header Packaging ===
            #ifdef ENABLE_LATENCY_PROBE
                // Format: [Timestamp(8B)] [Frame ID(1B)] [Packet ID(1B)] [Total(1B)]
                // Use memcpy to push double into byte stream
                uint8_t time_bytes[8];
                std::memcpy(time_bytes, &timestamp, 8);
                packet.insert(packet.end(), time_bytes, time_bytes + 8);
            #endif

            // Standard header
            packet.push_back(frame_id);
            packet.push_back((uint8_t)i);
            packet.push_back((uint8_t)num_packets);

            // Data body
            packet.insert(packet.end(), encoded.begin() + start_idx, encoded.begin() + end_idx);

            sendto(sock, packet.data(), packet.size(), 0, (const struct sockaddr *)&servaddr, sizeof(servaddr));
            usleep(150); // Slight flow control
        }

        frame_id++;
    }

    close(sock);
    return 0;
}