{
  lib,
  buildPythonPackage,
  fetchPypi,
  numpy,
  torch,
  torchaudio,
  einops,
}:

buildPythonPackage rec {
  pname = "encodec";
  version = "0.1.1";
  format = "setuptools";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-Nt3pjM/mxRoVV2R2yt/LOzWmNQe4uFVavWmImm+6Z3I=";
  };

  propagatedBuildInputs = [
    numpy
    torch
    torchaudio
    einops
  ];

  # Tests require additional dependencies and model files
  doCheck = false;

  pythonImportsCheck = [
    "encodec"
  ];

  meta = with lib; {
    description = "High fidelity neural audio codec";
    homepage = "https://github.com/facebookresearch/encodec";
    license = licenses.mit;
    maintainers = with maintainers; [ ];
  };
}
