{ pkgs, pythonPackages }:

let
  # Custom packages that aren't in nixpkgs
  encodec = pythonPackages.callPackage ./encodec.nix { };
  hangul_romanize = pythonPackages.callPackage ./hangul_romanize.nix { };
  TTS = pythonPackages.callPackage ./TTS.nix {
    inherit encodec hangul_romanize;
    inherit (pkgs) ffmpeg sox espeak;
  };
in
{
  inherit encodec hangul_romanize TTS;
}
