import os
import json
import csv
import ast
import re
from typing import Dict, List, Any, Tuple

class InspectionValidatorEngine:
    def __init__(self, resource_dir: str):
        self.resource_dir = os.path.abspath(resource_dir)

    def list_missions(self) -> List[Dict[str, Any]]:
        """Scans resource directory for available mission folders and CSV files."""
        missions = []
        if not os.path.exists(self.resource_dir):
            return missions

        for item in os.listdir(self.resource_dir):
            item_path = os.path.join(self.resource_dir, item)
            if os.path.isdir(item_path) and item.startswith("mission-"):
                mission_id = item.replace("mission-", "")
                csv_files = [f for f in os.listdir(item_path) if f.startswith("notification_") and f.endswith(".csv")]
                media_files = [
                    f for f in os.listdir(item_path) 
                    if f.endswith(('.jpg', '.png', '.mp4', '.wav', '.avi'))
                ]
                
                csv_path = os.path.join(item_path, csv_files[0]) if csv_files else None
                
                missions.append({
                    "id": mission_id,
                    "folder_name": item,
                    "folder_path": item_path,
                    "csv_file": csv_files[0] if csv_files else None,
                    "csv_path": csv_path,
                    "media_count": len(media_files),
                    "images_count": len([f for f in media_files if f.endswith(('.jpg', '.png'))]),
                    "videos_count": len([f for f in media_files if f.endswith(('.mp4', '.avi'))]),
                    "audio_count": len([f for f in media_files if f.endswith('.wav')])
                })
        
        missions.sort(key=lambda x: x["folder_name"])
        return missions

    def list_templates(self) -> List[Dict[str, Any]]:
        """Scans resource/path directory for available inspection template JSON files."""
        path_dir = os.path.join(self.resource_dir, "path")
        templates = []
        if not os.path.exists(path_dir):
            return templates

        for root, _, files in os.walk(path_dir):
            for file in files:
                if file.endswith(".json") and not file.endswith(".bak"):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, path_dir)
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                ins_count = sum(1 for item in data if item.get('PointInfo') == 1 or 'Inspection' in item)
                                templates.append({
                                    "filename": file,
                                    "rel_path": rel_path,
                                    "full_path": full_path,
                                    "total_waypoints": len(data),
                                    "inspection_points_count": ins_count,
                                    "file_size": os.path.getsize(full_path)
                                })
                    except Exception:
                        pass

        templates.sort(key=lambda x: x["filename"])
        return templates

    def parse_csv_literal(self, val_str: str) -> Any:
        """Safely parses Python dict/list literals or JSON strings from CSV."""
        if not val_str:
            return None
        val_str = val_str.strip()
        try:
            return json.loads(val_str)
        except Exception:
            pass
        try:
            return ast.literal_eval(val_str)
        except Exception:
            pass
        # Basic cleanup if single quotes
        try:
            cleaned = val_str.replace("True", "true").replace("False", "false").replace("None", "null")
            cleaned = cleaned.replace("'", '"')
            return json.loads(cleaned)
        except Exception:
            return val_str

    @staticmethod
    def compute_dev_evaluation(res_parsed: Any, level: str) -> str:
        """
        Evaluates prediction performance for dev verification:
        - TP (True Positive): Actual Anomaly Exists AND System Alerted
        - TN (True Negative): Normal State AND System Passed
        - FP (False Positive): Normal State BUT System Alerted (False Alarm)
        - FN (False Negative): Actual Anomaly Exists BUT System Passed (Missed Defect)
        """
        level_clean = str(level).lower().strip() if level else ''
        if level_clean in ['missing', 'n/a', 'none', '', 'null'] or res_parsed is None or res_parsed == '' or res_parsed == {}:
            return "N/A"
            
        sys_alerted = level_clean in ['critical', 'warning', 'error', 'alert'] or level_clean != 'pass'
        
        actual_anomaly = False
        if isinstance(res_parsed, dict):
            if "is_leak" in res_parsed:
                actual_anomaly = bool(res_parsed["is_leak"])
            elif "max_temperature" in res_parsed:
                actual_anomaly = float(res_parsed.get("max_temperature", 0)) >= 60.0
            elif "detection_status" in res_parsed:
                actual_anomaly = not bool(res_parsed["detection_status"])
            elif "kurtosis" in res_parsed or "peak_factor" in res_parsed:
                kurt = float(res_parsed.get("kurtosis", 0))
                peak = float(res_parsed.get("peak_factor", 0))
                actual_anomaly = kurt > 3.5 or peak > 4.5
            else:
                actual_anomaly = sys_alerted
        else:
            actual_anomaly = sys_alerted

        if actual_anomaly and sys_alerted:
            return "TP"
        elif not actual_anomaly and not sys_alerted:
            return "TN"
        elif not actual_anomaly and sys_alerted:
            return "FP"
        else:
            return "FN"

    def load_mission_data(self, mission_folder: str) -> Dict[str, Any]:
        """Loads and parses mission notification CSV and indexes all physical media files."""
        folder_path = os.path.abspath(mission_folder)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Mission directory not found: {mission_folder}")

        csv_files = [f for f in os.listdir(folder_path) if f.startswith("notification_") and f.endswith(".csv")]
        if not csv_files:
            raise FileNotFoundError(f"No notification CSV file found in {mission_folder}")

        csv_path = os.path.join(folder_path, csv_files[0])
        results = []
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                parsed_row = dict(row)
                parsed_row['result_parsed'] = self.parse_csv_literal(row.get('result', ''))
                parsed_row['files_parsed'] = self.parse_csv_literal(row.get('files', ''))
                parsed_row['dev_eval'] = self.compute_dev_evaluation(parsed_row['result_parsed'], row.get('notification_level', ''))
                results.append(parsed_row)

        # Index physical files in mission directory
        physical_files = {}
        for f in os.listdir(folder_path):
            file_path = os.path.join(folder_path, f)
            if os.path.isfile(file_path) and not f.startswith("."):
                physical_files[f] = {
                    "filename": f,
                    "size_bytes": os.path.getsize(file_path),
                    "ext": os.path.splitext(f)[1].lower()
                }

        return {
            "mission_folder": folder_path,
            "csv_filename": csv_files[0],
            "csv_path": csv_path,
            "results": results,
            "physical_files": physical_files
        }

    def merge_missing_points(self, csv_results: List[Dict[str, Any]], template_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compares CSV results against inspection template points and appends 
        synthetic missing records for any template points not found in CSV.
        """
        if not template_points:
            return csv_results

        existing_actions = set()
        for r in csv_results:
            action = (r.get("action_name") or "").strip()
            if action:
                existing_actions.add(action)

        combined_results = list(csv_results)
        
        for tp in template_points:
            node_info = (tp.get("node_info") or "").strip()
            if node_info and node_info not in existing_actions:
                combined_results.append({
                    "timestamp": "-",
                    "action_name": node_info,
                    "result": "{}",
                    "files": "[]",
                    "result_parsed": None,
                    "files_parsed": [],
                    "notification_level": "MISSING",
                    "dev_eval": "N/A",
                    "is_missing": True
                })

        return combined_results

    def load_template_data(self, template_path: str) -> Dict[str, Any]:
        """Loads and parses inspection template JSON."""
        full_path = os.path.abspath(template_path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Template JSON file not found: {template_path}")

        with open(full_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Template JSON must contain a top-level list of waypoint objects.")

        inspection_points = []
        via_points = []

        for idx, item in enumerate(data):
            node_info = item.get("Node_info", f"point-{idx}")
            point_info = item.get("PointInfo", 0)
            inspection_type = item.get("Inspection")

            point_record = {
                "template_index": idx,
                "node_info": node_info,
                "map_name": item.get("MapName"),
                "zone": item.get("Zone"),
                "map_id": item.get("MapID"),
                "value": item.get("Value"),
                "point_info": point_info,
                "inspection": inspection_type,
                "cam_ptz": item.get("CamPTZ"),
                "roi": item.get("Roi"),
                "threshold": item.get("Threshold"),
                "pos_x": item.get("PosX"),
                "pos_y": item.get("PosY"),
                "pos_z": item.get("PosZ"),
                "angle_yaw": item.get("AngleYaw"),
                "raw_item": item
            }

            if point_info == 1 or inspection_type:
                inspection_points.append(point_record)
            else:
                via_points.append(point_record)

        return {
            "template_path": full_path,
            "template_name": os.path.basename(full_path),
            "all_waypoints": data,
            "inspection_points": inspection_points,
            "via_points": via_points,
            "total_waypoints": len(data),
            "inspection_count": len(inspection_points),
            "via_count": len(via_points)
        }

    def validate(self, mission_folder: str, template_path: str) -> Dict[str, Any]:
        """
        Executes comprehensive 3-stage validation between Mission Results & Template.
        """
        mission_data = self.load_mission_data(mission_folder)
        template_data = self.load_template_data(template_path)

        csv_results = mission_data["results"]
        physical_files = mission_data["physical_files"]
        template_inspection_points = template_data["inspection_points"]

        issues = []
        coverage = {
            "matched": [],
            "missing_in_results": [],
            "extra_in_results": []
        }

        # Index CSV results by action_name and inspection_index
        csv_by_action = {}
        for r in csv_results:
            action = r.get("action_name", "").strip()
            if action:
                csv_by_action[action] = r

        # Index template inspection points by node_info
        template_by_node = {}
        for tp in template_inspection_points:
            node = tp.get("node_info", "").strip()
            if node:
                template_by_node[node] = tp

        # Check 1: Point Coverage Validation (Template vs CSV)
        matched_count = 0
        for node_info, tp in template_by_node.items():
            if node_info in csv_by_action:
                matched_count += 1
                coverage["matched"].append({
                    "node_info": node_info,
                    "template": tp,
                    "result": csv_by_action[node_info]
                })
            else:
                coverage["missing_in_results"].append({
                    "node_info": node_info,
                    "template": tp
                })
                issues.append({
                    "code": "MISSING_INSPECTION_POINT",
                    "severity": "ERROR",
                    "title": f"Missing Inspection: {node_info}",
                    "message": f"Node '{node_info}' is defined in template '{template_data['template_name']}' but was NOT found in mission CSV results.",
                    "node_info": node_info
                })

        for action_name, r in csv_by_action.items():
            if action_name not in template_by_node:
                coverage["extra_in_results"].append({
                    "action_name": action_name,
                    "result": r
                })
                issues.append({
                    "code": "UNEXPECTED_INSPECTION_POINT",
                    "severity": "WARNING",
                    "title": f"Extra Inspection Point: {action_name}",
                    "message": f"Action '{action_name}' is present in mission CSV results but NOT defined in template '{template_data['template_name']}'.",
                    "node_info": action_name
                })

        # Check 2: Media Files Verification (CSV references vs physical files on disk)
        referenced_files = set()
        file_check_ok = 0
        file_check_missing = 0
        file_check_empty = 0

        for r in csv_results:
            files_list = r.get("files_parsed", [])
            action_name = r.get("action_name", "")
            if isinstance(files_list, list):
                for f_item in files_list:
                    file_url = f_item.get("file_url", "") if isinstance(f_item, dict) else str(f_item)
                    fname = os.path.basename(file_url)
                    if fname:
                        referenced_files.add(fname)
                        if fname in physical_files:
                            file_info = physical_files[fname]
                            if file_info["size_bytes"] == 0:
                                file_check_empty += 1
                                issues.append({
                                    "code": "EMPTY_MEDIA_FILE",
                                    "severity": "ERROR",
                                    "title": f"Empty File: {fname}",
                                    "message": f"Media file '{fname}' referenced by '{action_name}' exists on disk but has 0 bytes.",
                                    "node_info": action_name,
                                    "filename": fname
                                })
                            else:
                                file_check_ok += 1
                        else:
                            file_check_missing += 1
                            issues.append({
                                "code": "MISSING_MEDIA_FILE",
                                "severity": "ERROR",
                                "title": f"Missing Media File: {fname}",
                                "message": f"File '{fname}' referenced in CSV for '{action_name}' does not exist in mission directory.",
                                "node_info": action_name,
                                "filename": fname
                            })

        # Detect Orphaned physical files (files on disk not referenced in CSV)
        orphaned_files = []
        for fname, f_info in physical_files.items():
            if fname not in referenced_files and fname != mission_data["csv_filename"]:
                orphaned_files.append(fname)
                issues.append({
                    "code": "ORPHANED_MEDIA_FILE",
                    "severity": "INFO",
                    "title": f"Orphaned Media File: {fname}",
                    "message": f"File '{fname}' exists in mission directory but is not referenced in the notification CSV.",
                    "filename": fname
                })

        # Check 3: Notification Level & Result Consistency Validation
        for r in csv_results:
            action_name = r.get("action_name", "")
            level = r.get("notification_level", "").lower()
            res_parsed = r.get("result_parsed", {})

            if isinstance(res_parsed, dict):
                # Check leakage rule
                if "is_leak" in res_parsed:
                    is_leak = res_parsed["is_leak"]
                    if is_leak and level != "critical":
                        issues.append({
                            "code": "LEVEL_MISMATCH",
                            "severity": "WARNING",
                            "title": f"Inconsistent Level for Leakage: {action_name}",
                            "message": f"Point '{action_name}' has is_leak=True, but notification_level is '{level}' (expected 'critical').",
                            "node_info": action_name
                        })
                # Check detection status rule
                if "detection_status" in res_parsed:
                    det_ok = res_parsed["detection_status"]
                    if not det_ok and level not in ["critical", "warning"]:
                        issues.append({
                            "code": "LEVEL_MISMATCH",
                            "severity": "WARNING",
                            "title": f"Inconsistent Level for Detection: {action_name}",
                            "message": f"Point '{action_name}' has detection_status=False, but notification_level is '{level}' (expected 'critical' or 'warning').",
                            "node_info": action_name
                        })

        # Confusion Matrix calculation for Dev evaluation
        tp_cnt = 0
        tn_cnt = 0
        fp_cnt = 0
        fn_cnt = 0

        for r in csv_results:
            eval_tag = r.get("dev_eval") or self.compute_dev_evaluation(r.get("result_parsed"), r.get("notification_level", ""))
            if eval_tag == "TP":
                tp_cnt += 1
            elif eval_tag == "TN":
                tn_cnt += 1
            elif eval_tag == "FP":
                fp_cnt += 1
            elif eval_tag == "FN":
                fn_cnt += 1

        total_eval = tp_cnt + tn_cnt + fp_cnt + fn_cnt
        acc = round(((tp_cnt + tn_cnt) / max(total_eval, 1)) * 100, 1)
        prec = round((tp_cnt / max(tp_cnt + fp_cnt, 1)) * 100, 1)
        rec = round((tp_cnt / max(tp_cnt + fn_cnt, 1)) * 100, 1)
        f1 = round((2 * prec * rec / max(prec + rec, 1)), 1)

        cm_dict = {
            "tp": tp_cnt,
            "tn": tn_cnt,
            "fp": fp_cnt,
            "fn": fn_cnt,
            "total": total_eval,
            "accuracy": acc,
            "precision": prec,
            "recall": rec,
            "f1_score": f1
        }

        # Health score calculation
        error_count = sum(1 for i in issues if i["severity"] == "ERROR")
        warning_count = sum(1 for i in issues if i["severity"] == "WARNING")
        info_count = sum(1 for i in issues if i["severity"] == "INFO")

        if error_count == 0 and warning_count == 0:
            status_label = "PASS"
            status_color = "success"
        elif error_count == 0:
            status_label = "WARNING"
            status_color = "warning"
        else:
            status_label = "FAIL"
            status_color = "danger"

        total_checks = len(template_inspection_points) + len(csv_results)
        coverage_pct = round((matched_count / max(len(template_inspection_points), 1)) * 100, 1)

        return {
            "summary": {
                "status": status_label,
                "status_color": status_color,
                "coverage_pct": coverage_pct,
                "total_template_inspections": len(template_inspection_points),
                "total_csv_results": len(csv_results),
                "matched_points": matched_count,
                "missing_points_count": len(coverage["missing_in_results"]),
                "extra_points_count": len(coverage["extra_in_results"]),
                "total_physical_files": len(physical_files),
                "referenced_files_count": len(referenced_files),
                "file_check_ok": file_check_ok,
                "file_check_missing": file_check_missing,
                "file_check_empty": file_check_empty,
                "orphaned_files_count": len(orphaned_files),
                "issues_count": len(issues),
                "errors_count": error_count,
                "warnings_count": warning_count,
                "info_count": info_count
            },
            "confusion_matrix": cm_dict,
            "coverage": coverage,
            "orphaned_files": orphaned_files,
            "issues": issues,
            "mission": {
                "folder_name": os.path.basename(mission_folder),
                "csv_filename": mission_data["csv_filename"]
            },
            "template": {
                "filename": template_data["template_name"],
                "total_waypoints": template_data["total_waypoints"]
            },
            "summary_report": self.get_summary_report(csv_results, template_inspection_points)
        }

    def get_summary_report(self, csv_results: List[Dict[str, Any]], template_inspection_points: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generates the Inspection Summary Report KPI & Breakdown table.
        """
        if template_inspection_points is None:
            template_inspection_points = []

        def classify_type(name: str) -> str:
            if not name:
                return "Other Inspection"
            lower = name.lower()
            if "asset" in lower:
                return "Asset Inspection"
            if "gauge" in lower:
                return "Gauge Inspection"
            if "leakage" in lower or "leak" in lower:
                return "Leakage Inspection"
            if "loto" in lower:
                return "Loto Inspection"
            if "thermal" in lower or "temp" in lower:
                return "Thermal Inspection"
            if "vibration" in lower or "vib" in lower:
                return "Vibration Inspection"
            return "Other Inspection"

        standard_types = [
            "Asset Inspection",
            "Gauge Inspection",
            "Leakage Inspection",
            "Loto Inspection",
            "Thermal Inspection",
            "Vibration Inspection"
        ]

        by_type = {t: {"pass_count": 0, "notification": 0, "missing": 0} for t in standard_types}

        csv_action_set = set()
        for r in csv_results:
            action = r.get("action_name", "").strip()
            if action:
                csv_action_set.add(action)
            
            ins_type = classify_type(action)
            if ins_type not in by_type:
                by_type[ins_type] = {"pass_count": 0, "notification": 0, "missing": 0}
            
            lvl = str(r.get("notification_level", "")).lower().strip()
            if lvl == "pass":
                by_type[ins_type]["pass_count"] += 1
            elif lvl in ["missing", "n/a", "none", ""]:
                by_type[ins_type]["missing"] += 1
            else:
                by_type[ins_type]["notification"] += 1

        for tp in template_inspection_points:
            node = tp.get("node_info", "").strip()
            ins_type = classify_type(node)
            if ins_type not in by_type:
                by_type[ins_type] = {"pass_count": 0, "notification": 0, "missing": 0}
            
            if node and node not in csv_action_set:
                by_type[ins_type]["missing"] += 1

        total_pass = 0
        total_notification = 0
        total_missing = 0
        total_points = 0

        breakdown = []
        for t_name, counts in by_type.items():
            row_total = counts["pass_count"] + counts["notification"] + counts["missing"]
            if row_total > 0 or t_name in standard_types:
                breakdown.append({
                    "inspection_type": t_name,
                    "pass_count": counts["pass_count"],
                    "notification": counts["notification"],
                    "missing": counts["missing"],
                    "total": row_total
                })
                total_pass += counts["pass_count"]
                total_notification += counts["notification"]
                total_missing += counts["missing"]
                total_points += row_total

        return {
            "kpi": {
                "total_points": total_points,
                "total_pass": total_pass,
                "notifications": total_notification,
                "missing_data": total_missing
            },
            "breakdown": breakdown,
            "totals_row": {
                "inspection_type": "Total",
                "pass_count": total_pass,
                "notification": total_notification,
                "missing": total_missing,
                "total": total_points
            }
        }
