from typing import List, Any, Dict, Optional, Union, Set, Type
from sqlalchemy import select, and_, or_, not_, text, join
from sqlalchemy.sql import Select
from src.models.base import Asset, Project, Base
from src.util.logging import Logger

class QueryBuilder:
    """Safe SQL query builder for assets and projects
    
    Query Specification Format:
    {
        "from": "assets" | "projects",  # Required: Base table
        "join": {  # Optional: Join specification
            "table": "assets" | "projects",
            "on": {  # Join conditions as field mappings
                "left_field": "right_field"  # e.g. "project_id": "id"
            }
        },
        "select": [  # Optional: Fields to select
            "table.field",  # e.g. "assets.id", "projects.name"
        ],
        "where": [  # Optional: List of conditions
            {
                "field": "table.field",  # e.g. "assets.asset_type"
                "op": "=" | "!=" | ">" | "<" | ">=" | "<=" | "like" | "ilike" | "in" | "not in" | "is null" | "is not null",
                "value": <any>  # Value to compare against
            }
        ],
        "order_by": [  # Optional: List of ordering specifications
            {
                "field": "table.field",  # e.g. "assets.created_at"
                "direction": "asc" | "desc"
            }
        ],
        "limit": <int>,  # Optional: Number of results to return
        "offset": <int>  # Optional: Number of results to skip
    }
    """
    
    def __init__(self):
        self.logger = Logger("QueryBuilder")
        self._table = None
        self._joins = []
        self._conditions = []
        self._order_by = []
        self._limit = None
        self._offset = None
        self._selected_fields = set()
        
    @classmethod
    def from_spec(cls, spec: Dict[str, Any]) -> 'QueryBuilder':
        """Create QueryBuilder from specification"""
        builder = cls()
        builder.logger.debug(f"Building query from spec: {spec}")
        
        # Get table name
        if "from" not in spec:
            raise ValueError("Query specification must include 'from' field")
        table_name = spec["from"]
        builder.logger.debug(f"Using table: {table_name}")
        
        # Set table
        builder.from_table(table_name)
        
        # Add join if specified
        if "join" in spec:
            if not isinstance(spec["join"], dict):
                raise ValueError("'join' must be a dictionary")
            if "table" not in spec["join"] or "on" not in spec["join"]:
                raise ValueError("Join specification must include 'table' and 'on' fields")
            builder.logger.debug(f"Adding join: {spec['join']}")
            builder.join(spec["join"]["table"], spec["join"]["on"])
            
        # Add select fields
        if "select" in spec:
            if not isinstance(spec["select"], list):
                raise ValueError("'select' must be a list of fields")
            builder.logger.debug(f"Adding select fields: {spec['select']}")
            builder.select(*spec["select"])
                
        # Add where conditions
        if "where" in spec:
            if not isinstance(spec["where"], list):
                raise ValueError("'where' must be a list of conditions")
            builder.logger.debug(f"Adding where conditions: {spec['where']}")
            for condition in spec["where"]:
                if not isinstance(condition, dict):
                    raise ValueError(f"Invalid where condition: {condition}")
                if "field" not in condition or "op" not in condition:
                    raise ValueError(f"Missing field or operator in condition: {condition}")
                    
                field = condition["field"]
                op = condition["op"]
                value = condition.get("value")
                
                builder.where(field, op, value)
                
        # Add order by
        if "order_by" in spec:
            builder.logger.debug(f"Adding order by: {spec['order_by']}")
            if isinstance(spec["order_by"], list):
                for order in spec["order_by"]:
                    if isinstance(order, dict):
                        if "field" not in order:
                            raise ValueError("Each order_by spec must include 'field'")
                        field = order["field"]
                        direction = order.get("direction", "asc")
                        builder.order_by(field, direction)
                    else:
                        builder.order_by(str(order))
            else:
                # Handle string format for RANDOM()
                builder.order_by(str(spec["order_by"]))
                
        # Add limit
        if "limit" in spec:
            builder.logger.debug(f"Setting limit: {spec['limit']}")
            builder.limit(spec["limit"])
            
        # Add offset
        if "offset" in spec:
            builder.logger.debug(f"Setting offset: {spec['offset']}")
            builder.offset(spec["offset"])
            
        return builder
        
    @classmethod
    def example_spec(cls) -> Dict:
        """Return an example query specification"""
        return {
            "from": "assets",
            "join": {
                "table": "projects",
                "on": {"project_id": "id"}
            },
            "select": ["assets.id", "assets.source_url", "projects.name"],
            "where": [
                {"field": "assets.asset_type", "op": "=", "value": "github_file"},
                {"field": "projects.platform", "op": "=", "value": "github"},
                {"field": "assets.source_url", "op": "like", "value": "github.com"}
            ],
            "order_by": [
                {"field": "assets.created_at", "direction": "desc"}
            ],
            "limit": 10
        }
        
    def from_table(self, table: Union[str, Type[Base]]) -> 'QueryBuilder':
        """Set the base table for the query"""
        if isinstance(table, str):
            if table.lower() == "assets":
                self._table = Asset
            elif table.lower() == "projects":
                self._table = Project
            else:
                raise ValueError(f"Invalid table name: {table}")
        else:
            self._table = table
        return self
        
    def join(self, table_name: str, on: Dict[str, str]) -> 'QueryBuilder':
        """Add a JOIN clause
        
        Args:
            table_name: Name of table to join with
            on: Dictionary of join conditions, e.g. {"project_id": "id"} for assets.project_id = projects.id
        """
        if not self._table:
            raise ValueError("No base table selected. Call from_table() first.")
            
        # Determine the table to join with
        if table_name.lower() == "assets":
            join_table = Asset
        elif table_name.lower() == "projects":
            join_table = Project
        else:
            raise ValueError(f"Invalid table name: {table_name}")
            
        # Validate and build join conditions
        join_conditions = []
        for left_field, right_field in on.items():
            # Validate fields exist
            if not hasattr(self._table, left_field):
                raise ValueError(f"Field {left_field} does not exist in {self._table.__name__}")
            if not hasattr(join_table, right_field):
                raise ValueError(f"Field {right_field} does not exist in {join_table.__name__}")
                
            # Build join condition
            left = getattr(self._table, left_field)
            right = getattr(join_table, right_field)
            join_conditions.append(left == right)
            
        # Add join to list
        self._joins.append((join_table, and_(*join_conditions)))
        return self
        
    def select(self, *fields: str) -> 'QueryBuilder':
        """Add fields to select
        
        Args:
            fields: Field names to select, e.g. "assets.id", "projects.name"
        """
        if not self._table:
            raise ValueError("No table selected. Call from_table() first.")
            
        for field in fields:
            # Require table.field format
            if "." not in field:
                raise ValueError(f"Invalid field format: {field}. Use format 'table.field'")
                
            try:
                table_name, field_name = field.split(".")
            except ValueError:
                raise ValueError(f"Invalid field format: {field}. Use format 'table.field'")
            
            if table_name.lower() == "assets":
                table = Asset
            elif table_name.lower() == "projects":
                table = Project
            else:
                raise ValueError(f"Invalid table name: {table_name}")
                
            if not hasattr(table, field_name):
                raise ValueError(f"Field {field_name} does not exist in {table.__name__}")
                
            self._selected_fields.add(getattr(table, field_name))
            
        return self
        
    def where(self, field: str, operator: str, value: Any) -> 'QueryBuilder':
        """Add a WHERE condition"""
        allowed_operators = {
            "=": lambda f, v: f == v,
            "!=": lambda f, v: f != v,
            ">": lambda f, v: f > v,
            "<": lambda f, v: f < v,
            ">=": lambda f, v: f >= v,
            "<=": lambda f, v: f <= v,
            "like": lambda f, v: f.like(f"%{v}%"),
            "ilike": lambda f, v: f.ilike(f"%{v}%"),
            "in": lambda f, v: f.in_(v if isinstance(v, (list, tuple)) else [v]),
            "not in": lambda f, v: ~f.in_(v if isinstance(v, (list, tuple)) else [v]),
            "is null": lambda f, _: f.is_(None),
            "is not null": lambda f, _: f.isnot(None),
            "?": lambda f, v: text(f"{f.key} ? :value").bindparams(value=v),
            "?*": lambda f, v: text(f"EXISTS (SELECT 1 FROM json_array_elements_text({f.key}::json) as elem WHERE lower(elem) = lower(:value))").bindparams(value=v)
        }
        
        if operator not in allowed_operators:
            raise ValueError(f"Invalid operator: {operator}. Allowed operators: {', '.join(allowed_operators.keys())}")
            
        # Handle table.field format
        if "." in field:
            table_name, field_name = field.split(".")
            if table_name.lower() == "assets":
                table = Asset
            elif table_name.lower() == "projects":
                table = Project
            else:
                raise ValueError(f"Invalid table name: {table_name}")
        else:
            if not self._table:
                raise ValueError("No table selected. Call from_table() first.")
            table = self._table
            field_name = field
            
        if not hasattr(table, field_name):
            raise ValueError(f"Invalid field: {field_name}. Field does not exist in table {table.__name__}")
            
        table_field = getattr(table, field_name)
        self._conditions.append(allowed_operators[operator](table_field, value))
            
        return self
        
    def order_by(self, field: str, direction: str = "asc") -> 'QueryBuilder':
        """Add an ORDER BY clause
        
        Args:
            field: Field name or SQL function (e.g. "created_at" or "RANDOM()")
            direction: Sort direction ("asc" or "desc")
        """
        if direction.lower() not in ("asc", "desc"):
            raise ValueError("Direction must be either 'asc' or 'desc'")
            
        # Handle SQL functions
        if field.upper().endswith("()"):
            self._order_by.append(text(field))
            return self
            
        # Handle table.field format
        if "." in field:
            table_name, field_name = field.split(".")
            if table_name.lower() == "assets":
                table = Asset
            elif table_name.lower() == "projects":
                table = Project
            else:
                raise ValueError(f"Invalid table name: {table_name}")
        else:
            if not self._table:
                raise ValueError("No table selected. Call from_table() first.")
            table = self._table
            field_name = field
            
        if not hasattr(table, field_name):
            raise ValueError(f"Invalid field: {field_name}. Field does not exist in table {table.__name__}")
            
        table_field = getattr(table, field_name)
        if direction.lower() == "asc":
            self._order_by.append(table_field.asc())
        else:
            self._order_by.append(table_field.desc())
            
        return self
        
    def limit(self, limit: int) -> 'QueryBuilder':
        """Add LIMIT clause"""
        if not isinstance(limit, int) or limit < 0:
            raise ValueError("Limit must be a positive integer")
        self._limit = limit
        return self
        
    def offset(self, offset: int) -> 'QueryBuilder':
        """Add OFFSET clause"""
        if not isinstance(offset, int) or offset < 0:
            raise ValueError("Offset must be a positive integer")
        self._offset = offset
        return self
        
    def build(self) -> Select:
        """Build and return the SQLAlchemy query"""
        if not self._table:
            raise ValueError("No table selected. Call from_table() first.")
            
        # Start with base query
        if self._selected_fields:
            query = select(*self._selected_fields)
        else:
            query = select(self._table)
            
        # Add JOINs
        for join_table, join_condition in self._joins:
            query = query.join(join_table, join_condition)
            
        # Add WHERE conditions
        if self._conditions:
            query = query.where(and_(*self._conditions))
            
        # Add ORDER BY
        if self._order_by:
            query = query.order_by(*self._order_by)
            
        # Add LIMIT and OFFSET
        if self._limit is not None:
            query = query.limit(self._limit)
        if self._offset is not None:
            query = query.offset(self._offset)
            
        self.logger.debug(f"Built query: {query}")
        return query
        
    def __str__(self) -> str:
        """Return the SQL string representation of the query"""
        return str(self.build().compile(compile_kwargs={"literal_binds": True}))
        
    @classmethod
    def example(cls) -> str:
        """Return example usage of the query builder"""
        return """
        # Example usage:
        query = (QueryBuilder()
            .from_table("assets")
            .join("projects", {"project_id": "id"})
            .select("assets.id", "assets.source_url", "projects.name")
            .where("projects.platform", "=", "github")
            .where("assets.asset_type", "=", "github_file")
            .order_by("assets.created_at", "desc")
            .limit(10)
            .build()
        )
        """ 