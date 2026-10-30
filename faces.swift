// Prints one JSON line per image: {"f": path, "faces": [[cx, cy, w, h], ...]} in 0-1 image coords, top-left origin.
import Foundation
import Vision
import AppKit

for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNDetectFaceRectanglesRequest()
    try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    let faces = (req.results ?? []).map { r -> [Double] in
        let b = r.boundingBox
        return [Double(b.midX), Double(1 - b.midY), Double(b.width), Double(b.height)].map { ($0 * 1000).rounded() / 1000 }
    }
    let data = try! JSONSerialization.data(withJSONObject: ["f": path, "faces": faces])
    print(String(data: data, encoding: .utf8)!)
}
