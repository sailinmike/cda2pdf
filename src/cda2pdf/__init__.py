# Copyright (C) 2026 Mint Medical PLLC
#
# This file is part of cda2pdf.
#
# cda2pdf is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# cda2pdf is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE. See the GNU Affero General Public License for details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""cda2pdf — Convert HL7 CDA R2 XML files and IHE XDM clinical packages into bookmarked PDFs."""

from .converter import CDAPackageConverter, ConversionResult, convert_cda_to_pdf
from .parser import CDADocumentParsed, PatientDemographics, is_cda_xml, parse_cda_xml

__version__ = "0.1.0"
__all__ = [
    "CDAPackageConverter",
    "ConversionResult",
    "convert_cda_to_pdf",
    "CDADocumentParsed",
    "PatientDemographics",
    "is_cda_xml",
    "parse_cda_xml",
    "__version__",
]
