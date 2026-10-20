// Foreground matte with Apple Vision: swift matte.swift <in.png> <mask-out.png>
// Writes a greyscale mask (white = subject) at the input's size.
import Foundation
import Vision
import CoreImage
import CoreImage.CIFilterBuiltins

let args = CommandLine.arguments
let input = URL(fileURLWithPath: args[1]), output = URL(fileURLWithPath: args[2])
let ci = CIImage(contentsOf: input)!
let handler = VNImageRequestHandler(ciImage: ci)
let req = VNGenerateForegroundInstanceMaskRequest()
try handler.perform([req])
guard let obs = req.results?.first else { fatalError("no foreground found") }
let buf = try obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: handler)
let mask = CIImage(cvPixelBuffer: buf)
let ctx = CIContext()
try ctx.writePNGRepresentation(of: mask, to: output, format: .L8, colorSpace: CGColorSpaceCreateDeviceGray())
print("ok", mask.extent)
