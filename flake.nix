{
  description = "Glowtalk - Generate audiobooks for Glowfics";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Import the existing default.nix with the current pkgs
        glowtalkPackage = (import ./default.nix { inherit pkgs; }).package;

        # Create the development shell based on shell.nix
        devShell = import ./shell.nix { inherit pkgs; };
      in
      {
        # Export the package
        packages.default = glowtalkPackage;
        packages.glowtalk = glowtalkPackage;

        # Development shell for `nix develop`
        devShells.default = devShell;

        # Apps for running the application
        apps.default = {
          type = "app";
          program = "${glowtalkPackage}/bin/glowtalk";
        };
      }
    );
}
