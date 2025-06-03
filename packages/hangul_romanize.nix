{ lib
, buildPythonPackage
, fetchPypi
}:

buildPythonPackage rec {
  pname = "hangul-romanize";
  version = "0.1.0";
  format = "setuptools";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-+uaboYGvbnWoZGD9f1emswTNXxlz2MQl7YYC/uLJJ2w=";
  };

  # No dependencies needed
  propagatedBuildInputs = [ ];

  # Package has no tests
  doCheck = false;

  pythonImportsCheck = [
    "hangul_romanize"
  ];

  meta = with lib; {
    description = "Romanize Hangul strings";
    homepage = "https://github.com/youknowone/hangul-romanize";
    license = licenses.mit; # Assuming MIT based on common practice
    maintainers = with maintainers; [ ];
  };
}
