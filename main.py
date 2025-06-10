from collections import deque
import pygame
import json
import random
from enum import Enum

# 初始化pygame
pygame.init()

# 游戏常量
WINDOW_WIDTH = 1300
WINDOW_HEIGHT = 850

GAME_WIDTH = 1100
GAME_HEIGHT = 850
UI_WIDTH = 200
ENEMY_WIDTH = 50
ENEMY_HEIGHT = 40

start_time = pygame.time.get_ticks()

# 颜色定义
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
BROWN = (139, 69, 19)
GRAY = (128, 128, 128)
DARK_GREEN = (0, 128, 0)
ORANGE = (255, 165, 0)


# 游戏状态
class GameState(Enum):
    MENU = 1
    PLAYING = 2
    GAME_OVER = 3
    VICTORY = 4
    LEVEL_SELECT = 5


# 障碍物类型
class ObstacleType(Enum):
    WALL = 1
    SWAMP = 2
    TRAP = 3
    ENEMY = 4


def load_chinese_font(size):
    """加载支持中文的字体"""
    chinese_fonts = 'SimHei'
    font = pygame.font.SysFont(chinese_fonts, size)
    return font


def play_background_music(music_path, loop=-1, volume=0.5):
    pygame.mixer.music.load(music_path)
    pygame.mixer.music.play(loops=loop)
    pygame.mixer.music.set_volume(volume)


class Player:
    def __init__(self, x, y, size=60):
        self.speed = 3
        self.health = 100
        self.max_health = 100
        self.in_swamp = False
        self.size = size
        self.direction = 1

        self.invincible = False  # 无敌状态
        self.invincible_time = 0  # 无敌时间
        # 加载玩家图片
        self.image_left = pygame.image.load(".\image\player_left.png").convert_alpha()
        self.image_left = pygame.transform.scale(self.image_left, (self.size, self.size))  # 缩放图片
        self.image_left = enhance_color_saturation(self.image_left, 3)

        self.image_right = pygame.image.load(".\image\player_right.png").convert_alpha()
        self.image_right = pygame.transform.scale(self.image_right, (self.size, self.size))  # 缩放图片
        self.image_right = enhance_color_saturation(self.image_right, 3)

        self.image = self.image_right
        self.rect = self.image.get_rect(topleft=(x, y))  # 使用 rect 管理位置

    def move(self, dx, dy, obstacles):
        speed = self.speed // 2 if self.in_swamp else self.speed

        # 分别处理水平移动
        if dx != 0:
            self.rect.x += dx * speed
            if dx > 0:
                self.direction = 1
                self.image = self.image_right
            elif dx < 0:
                self.direction = -1
                self.image = self.image_left

            # 水平方向边界检查
            if self.rect.left < 0:
                self.rect.left = 0  # 限制在左边界内
            elif self.rect.right > GAME_WIDTH:
                self.rect.right = GAME_WIDTH  # 限制在右边界内

            # 水平方向障碍物检查
            for obstacle in obstacles:
                if obstacle.type == ObstacleType.WALL and self.rect.colliderect(obstacle.rect):
                    # 回退水平移动
                    self.rect.x -= dx * speed
                    break

        # 分别处理垂直移动
        if dy != 0:
            self.rect.y += dy * speed

            # 垂直方向边界检查
            if self.rect.top < 0:
                self.rect.top = 0  # 限制在上边界内
            elif self.rect.bottom > GAME_HEIGHT:
                self.rect.bottom = GAME_HEIGHT  # 限制在下边界内

            # 垂直方向障碍物检查
            for obstacle in obstacles:
                if obstacle.type == ObstacleType.WALL and self.rect.colliderect(obstacle.rect):
                    # 回退垂直移动
                    self.rect.y -= dy * speed
                    break

        return True  # 移动已处理（可能部分被阻挡）

    def check_obstacles(self, obstacles):
        self.in_swamp = False
        for obstacle in obstacles:
            if obstacle.type == ObstacleType.ENEMY:
                temp_rect = obstacle.rect.inflate(-20, -20)
                if temp_rect.colliderect(self.rect):
                    return True

            if self.rect.colliderect(obstacle.rect):
                if obstacle.type == ObstacleType.SWAMP:
                    self.in_swamp = True
                elif obstacle.type == ObstacleType.TRAP:
                    self.health -= 0.5

        return False

    def draw(self, screen):
        screen.blit(self.image, self.rect)  # 绘制图片

        # 血量条
        health_x = self.rect.x + (self.rect.width - 30) // 2
        health_y = self.rect.y - 8
        pygame.draw.rect(screen, RED, (health_x, health_y, 30, 4))
        current_health = int(30 * (self.health / self.max_health))
        pygame.draw.rect(screen, GREEN, (health_x, health_y, current_health, 4))

        if not self.invincible or (self.invincible_time // 200) % 2 == 0:
            screen.blit(self.image, self.rect)

        # 显示无敌时间倒计时
        if self.invincible:
            remaining_time = max(0, 2000 - (pygame.time.get_ticks() - start_time)) // 100
            font = load_chinese_font(15)
            text = font.render(f"无敌: {remaining_time / 10:.1f}s", True, (0, 0, 0))
            screen.blit(text, (self.rect.x, self.rect.y - 20))


class Obstacle:
    def __init__(self, x, y, width, height, obstacle_type):
        self.rect = pygame.Rect(x, y, width, height)
        self.type = obstacle_type

        self.image = None
        self.image_right = None
        self.image_left = None

        self.grid_size = 20  # 寻路网格大小
        self.bfs_path = deque()  # BFS计算出的路径
        self.last_bfs_update = 0  # 上次BFS更新的时间
        self.bfs_update_interval = 50  # BFS更新间隔(毫秒)
        self.chase_range = 300  # 追击范围
        self.chase_speed = 2.0  # 追击速度
        self.in_swamp = False
        self.swap_speed = 1.0
        self.speed = 2.0

        # 敌人特有属性
        if obstacle_type == ObstacleType.ENEMY:
            self.path = []
            self.path_index = 0
            self.move_speed = 1
            self.original_x = x
            self.original_y = y

            self.image_left = pygame.image.load(".\image\enemy_left.png").convert_alpha()
            self.image_left = pygame.transform.scale(self.image_left, (width, height))  # 缩放图片

            self.image_right = pygame.image.load(".\image\enemy_right.png").convert_alpha()
            self.image_right = pygame.transform.scale(self.image_right, (width, height))

            self.image = self.image_right  # 默认向右
            self.direction = 1  # 1=右，-1=左
        else:
            self.color = self._get_color()  # 其他类型使用颜色

    def _get_color(self):
        color_map = {
            ObstacleType.WALL: GRAY,
            ObstacleType.SWAMP: DARK_GREEN,
            ObstacleType.TRAP: RED,
            ObstacleType.ENEMY: PURPLE
        }
        return color_map.get(self.type, BLACK)

    def calculate_bfs_path(self, game_map, player_pos, obstacles):
        grid_cols = GAME_WIDTH // self.grid_size
        grid_rows = GAME_HEIGHT // self.grid_size
        grid = [[True for _ in range(grid_rows)] for _ in range(grid_cols)]

        # 正确标记障碍物（只考虑墙壁）
        for obstacle in obstacles:
            if obstacle.type == ObstacleType.WALL:
                start_x = obstacle.rect.left // self.grid_size
                end_x = (obstacle.rect.right // self.grid_size) + 1
                start_y = obstacle.rect.top // self.grid_size
                end_y = (obstacle.rect.bottom // self.grid_size) + 1

                for x in range(start_x, min(end_x, grid_cols)):
                    for y in range(start_y, min(end_y, grid_rows)):
                        if 0 <= x < grid_cols and 0 <= y < grid_rows:
                            grid[x][y] = False

        # 坐标转换（修复）
        start_x = self.rect.centerx // self.grid_size
        start_y = self.rect.centery // self.grid_size
        end_x = player_pos[0] // self.grid_size
        end_y = player_pos[1] // self.grid_size

        # BFS算法（修正队列操作）
        queue = deque()
        queue.append((start_x, start_y))  # 修复语法
        visited = [[False] * grid_rows for _ in range(grid_cols)]
        parent = [[None] * grid_rows for _ in range(grid_cols)]
        directions = [(0, -1), (1, 0), (0, 1), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]  # 上右下左

        while queue:
            x, y = queue.popleft()
            if (x, y) == (end_x, end_y):
                # 回溯路径（修复坐标转换）
                path = deque()
                while (x, y) != (start_x, start_y):
                    # 转换为世界坐标（网格中心点）
                    world_x = x * self.grid_size + self.grid_size // 2
                    world_y = y * self.grid_size + self.grid_size // 2
                    path.appendleft((world_x, world_y))
                    x, y = parent[x][y]
                return path

            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if (0 <= nx < grid_cols and 0 <= ny < grid_rows
                        and grid[nx][ny] and not visited[nx][ny]):
                    visited[nx][ny] = True
                    parent[nx][ny] = (x, y)
                    queue.append((nx, ny))  # 修复语法

        return deque()  # 无路径

    def update(self, game_map=None, player=None, obstacles=None):
        if self.type == ObstacleType.ENEMY and self.path:
            current_time = pygame.time.get_ticks()
            # 检查与SWAMP类型障碍物的碰撞并减速
            self.in_swamp = False
            if obstacles:
                for obstacle in obstacles:
                    if obstacle.type == ObstacleType.SWAMP and self.rect.colliderect(obstacle.rect):
                        self.in_swamp = True
                        # self.speed = self.chase_speed * 0.5  # 只对SWAMP类型减速50%
                        break  # 只应用第一个碰到的减速区域效果
            if self.in_swamp:
                self.speed = self.swap_speed
            else:
                self.speed = self.chase_speed

            if player:
                # 计算与玩家的距离
                dx = player.rect.centerx - self.rect.centerx
                dy = player.rect.centery - self.rect.centery
                dist_to_player = (dx ** 2 + dy ** 2) ** 0.5

                # 追击玩家
                if dist_to_player < self.chase_range:
                    # 定期更新BFS路径
                    if current_time - self.last_bfs_update > self.bfs_update_interval or not self.bfs_path:
                        self.bfs_path = self.calculate_bfs_path(game_map, player.rect.center, obstacles)
                        self.last_bfs_update = current_time

                    # 如果有BFS路径，沿着路径移动
                    if self.bfs_path:
                        target = self.bfs_path[0]
                        target_x, target_y = target

                        # 计算到目标点的方向
                        dx = target_x - self.rect.centerx
                        dy = target_y - self.rect.centery
                        distance = max(1, (dx ** 2 + dy ** 2) ** 0.5)

                        # 移动到目标点
                        self.rect.x += (dx / distance) * self.speed
                        self.rect.y += (dy / distance) * self.speed

                        # 更新方向
                        if dx > 0:
                            self.image = self.image_right
                        elif dx < 0:
                            self.image = self.image_left

                        # 如果接近目标点，移动到下一个点
                        if distance < self.speed * 2:
                            self.bfs_path.popleft()

                        return

                    # 如果没有BFS路径，直接向玩家移动
                    dx = player.rect.centerx - self.rect.centerx
                    dy = player.rect.centery - self.rect.centery
                    distance = max(1, (dx ** 2 + dy ** 2) ** 0.5)

                    # 移动敌人
                    self.rect.x += (dx / distance) * self.speed
                    self.rect.y += (dy / distance) * self.speed

                    # 更新方向
                    if dx > 0:
                        self.image = self.image_right
                    elif dx < 0:
                        self.image = self.image_left

                    return

            # 更新方向
            if dx > 0:
                self.image = self.image_right
            elif dx < 0:
                self.image = self.image_left

    def set_patrol_path(self, path):
        """设置敌人巡逻路径"""
        if self.type == ObstacleType.ENEMY:
            self.path = path
            self.path_index = 0

    def draw(self, screen):
        if self.type == ObstacleType.ENEMY and self.image:
            screen.blit(self.image, self.rect)
        else:
            pygame.draw.rect(screen, self.color, self.rect)


class Level:
    def __init__(self, level_data):
        self.start_pos = level_data.get('start', (50, 50))
        self.end_pos = level_data.get('end', (GAME_WIDTH - 100, GAME_HEIGHT - 100))
        self.obstacles = []
        self._load_obstacles(level_data.get('obstacles', []))

    def _load_obstacles(self, obstacle_data):
        for obs in obstacle_data:
            obstacle_type = ObstacleType(obs['type'])
            obstacle = Obstacle(obs['x'], obs['y'], obs['width'], obs['height'], obstacle_type)

            # 如果是敌人，设置巡逻路径
            if obstacle_type == ObstacleType.ENEMY and 'path' in obs:
                obstacle.set_patrol_path(obs['path'])

            self.obstacles.append(obstacle)

    def draw(self, screen):
        # 绘制起点
        pygame.draw.rect(screen, GREEN, (*self.start_pos, 30, 30))
        pygame.draw.rect(screen, BLACK, (*self.start_pos, 30, 30), 2)

        # 绘制终点
        pygame.draw.rect(screen, YELLOW, (*self.end_pos, 40, 40))
        pygame.draw.rect(screen, BLACK, (*self.end_pos, 40, 40), 2)

        # 绘制障碍物
        for obstacle in self.obstacles:
            obstacle.draw(screen)


class MazeGenerator:
    @staticmethod
    def generate_random_level(width=GAME_WIDTH, height=GAME_HEIGHT):
        """生成随机关卡"""
        level_data = {
            'start': (20, 20),
            'end': (width - 60, height - 60),
            'obstacles': []
        }

        def is_overlapping(obstacle1, obstacle2):
            """检查两个障碍是否重叠"""
            x1, y1, w1, h1 = obstacle1['x'], obstacle1['y'], obstacle1['width'], obstacle1['height']
            x2, y2, w2, h2 = obstacle2['x'], obstacle2['y'], obstacle2['width'], obstacle2['height']
            return (x1 < x2 + w2 and x1 + w1 > x2 and
                    y1 < y2 + h2 and y1 + h1 > y2)

        def is_near_start_end(obstacle):
            """检查障碍是否在起点或终点附近"""
            start_x, start_y = level_data['start']
            end_x, end_y = level_data['end']
            x, y, w, h = obstacle['x'], obstacle['y'], obstacle['width'], obstacle['height']
            near_start = (abs(x - start_x) < 100 and abs(y - start_y) < 100)
            near_end = (abs(x - end_x) < 100 and abs(y - end_y) < 100)
            return near_start or near_end

        # 生成随机墙壁
        while len(level_data['obstacles']) < 15:
            x = random.randint(0, width - 100)
            y = random.randint(0, height - 50)
            w = random.randint(20, 100)
            h = random.randint(20, 50)
            new_obstacle = {
                'x': x, 'y': y, 'width': w, 'height': h, 'type': 1
            }
            if not any(is_overlapping(new_obstacle, obs) for obs in level_data['obstacles']) \
                    and not is_near_start_end(new_obstacle):
                level_data['obstacles'].append(new_obstacle)

        # 生成沼泽
        while len([obs for obs in level_data['obstacles'] if obs['type'] == 2]) < 8:
            x = random.randint(0, width - 80)
            y = random.randint(0, height - 80)
            new_obstacle = {
                'x': x, 'y': y, 'width': 60, 'height': 60, 'type': 2
            }
            if not any(is_overlapping(new_obstacle, obs) for obs in level_data['obstacles']) \
                    and not is_near_start_end(new_obstacle):
                level_data['obstacles'].append(new_obstacle)

        # 生成陷阱
        while len([obs for obs in level_data['obstacles'] if obs['type'] == 3]) < 10:
            x = random.randint(0, width - 30)
            y = random.randint(0, height - 30)
            new_obstacle = {
                'x': x, 'y': y, 'width': 25, 'height': 25, 'type': 3
            }
            if not any(is_overlapping(new_obstacle, obs) for obs in level_data['obstacles']) \
                    and not is_near_start_end(new_obstacle):
                level_data['obstacles'].append(new_obstacle)

        # 生成移动敌人
        while len([obs for obs in level_data['obstacles'] if obs['type'] == 4]) < 4:
            x = random.randint(100, width - 200)
            y = random.randint(100, height - 200)
            path = [(x, y), (x + 100, y), (x + 100, y + 50), (x, y + 50)]
            new_obstacle = {
                'x': x, 'y': y, 'width': ENEMY_WIDTH, 'height': ENEMY_HEIGHT, 'type': 4, 'path': path
            }
            if not any(is_overlapping(new_obstacle, obs) for obs in level_data['obstacles']) \
                    and not is_near_start_end(new_obstacle):
                level_data['obstacles'].append(new_obstacle)

        return level_data


class Game:
    def __init__(self):
        self.music_list = ['./music/哈基米大冒险.mp3', './music/normal_no_more.mp3', './music/223AM.mp3',
                           './music/Color-X.mp3']
        self.name_list = ['哈基米大冒险', 'normal_no_more', '223AM', 'Color-X']
        self.owner_list = ['网易云 芸风墨客', '网易云 还给我神ID', '网易云 还给我神ID', '网易云 萧凌玖']

        self.volume_step = 0.1
        self.current_music_index = 0
        self.volume = 0.5
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("迷宫探险")
        self.clock = pygame.time.Clock()

        # 加载字体
        self.huge_font = load_chinese_font(100)
        self.big_font = load_chinese_font(40)

        self.font = load_chinese_font(36)
        self.small_font = load_chinese_font(24)
        self.tiny_font = load_chinese_font(18)

        self.state = GameState.MENU
        self.player = None
        self.level = None
        self.start_time = 0
        self.current_time = 0
        self.score = 0
        self.current_level_num = 1
        self.enemy = None

        # 预定义关卡
        self.levels = self._load_predefined_levels()
        self.background_img = pygame.image.load(".\image\menu_background.jpg").convert()

        self.player_img = pygame.image.load(".\image\player_right.png").convert_alpha()  # 玩家图片（带透明通道）
        self.enemy_img = pygame.image.load(".\image\enemy_right.png").convert_alpha()  # 玩家图片（带透明通道）

        self.player_img = pygame.transform.scale(self.player_img, (120, 120))  # 缩放图片
        self.enemy_img = pygame.transform.scale(self.enemy_img, (120, 75))  # 缩放图片

        # 初始化图片位置（根据图片尺寸调整初始坐标）
        self.animation_positions = {
            "player": -self.player_img.get_width(),  # 玩家初始位置：完全在屏幕左侧外
            "enemy": -self.enemy_img.get_width() * 3  # 敌人初始位置：更靠左，实现追逐延迟
        }

    def _load_predefined_levels(self):
        """加载预定义关卡"""
        levels = []
        # 关卡1：简单教学关卡
        level1 = {
            'start': (20, 20),
            'end': (1000, 750),
            'obstacles': [
                {'x': 200, 'y': 100, 'width': 20, 'height': 500, 'type': 1},
                {'x': 500, 'y': 300, 'width': 500, 'height': 20, 'type': 1},
                {'x': 400, 'y': 400, 'width': 150, 'height': 150, 'type': 2},
                {'x': 500, 'y': 100, 'width': 60, 'height': 60, 'type': 3},
                {'x': 800, 'y': 500, 'width': ENEMY_WIDTH, 'height': ENEMY_HEIGHT, 'type': 4,
                 'path': [(600, 300), (650, 300), (650, 350), (600, 350)]},
            ]
        }
        levels.append(level1)

        # 关卡2：中等难度
        level2 = {
            'start': (50, 50),
            'end': (1000, 750),
            'obstacles': [
                {'x': 200, 'y': 0, 'width': 20, 'height': 500, 'type': 1},
                {'x': 500, 'y': 200, 'width': 20, 'height': 500, 'type': 1},
                {'x': 800, 'y': 0, 'width': 20, 'height': 500, 'type': 1},
                {'x': 200, 'y': 150, 'width': 200, 'height': 100, 'type': 2},
                {'x': 500, 'y': 350, 'width': 200, 'height': 100, 'type': 2},
                {'x': 400, 'y': 100, 'width': 80, 'height': 80, 'type': 3},
                {'x': 850, 'y': 150, 'width': ENEMY_WIDTH, 'height': ENEMY_HEIGHT, 'type': 4,
                 'path': [(600, 100), (700, 100), (700, 200), (600, 200)]},
                {'x': 530, 'y': 650, 'width': ENEMY_WIDTH, 'height': ENEMY_HEIGHT, 'type': 4,
                 'path': [(250, 450), (350, 450), (350, 500), (250, 500)]},
            ]
        }
        levels.append(level2)

        return levels

    def start_level(self, level_num):
        """开始指定关卡"""
        print(f"开始关卡 {level_num}")
        if level_num <= len(self.levels):
            level_data = self.levels[level_num - 1]
        else:
            # 生成随机关卡
            level_data = MazeGenerator.generate_random_level()

        self.level = Level(level_data)
        self.player = Player(*self.level.start_pos)
        self.start_time = pygame.time.get_ticks()
        global start_time
        start_time = self.start_time
        self.state = GameState.PLAYING
        self.current_level_num = level_num  # 更新关卡编号，用于处理进入下一关的逻辑

    def handle_input(self):
        keys = pygame.key.get_pressed()
        if self.state == GameState.PLAYING and self.player:
            dx, dy = 0, 0
            if keys[pygame.K_w] or keys[pygame.K_UP]:  # 方向键 或 wsad
                dy = -1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                dy = 1
            if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                dx = -1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                dx = 1

            if dx != 0 or dy != 0:
                self.player.move(dx, dy, self.level.obstacles)

    def update(self):
        if self.state == GameState.PLAYING:
            self.current_time = pygame.time.get_ticks() - self.start_time
            self.player.invincible = self.current_time <= 2000  # 3秒无敌时间
            self.player.invincible_time = self.current_time  # 记录无敌时间用于闪烁效果
            # 更新障碍物（主要是敌人）
            for obstacle in self.level.obstacles:
                # 传递当前关卡的所有障碍物
                obstacle.update(player=self.player, obstacles=self.level.obstacles)

            if self.current_time <= 2000:
                return

            # 检查玩家与障碍物的碰撞
            if not self.player.invincible and self.player.check_obstacles(self.level.obstacles):
                print("碰到敌人，游戏结束")
                self.state = GameState.GAME_OVER

            # 检查生命值
            if self.player.health <= 0:
                print("生命值为0，游戏结束")
                self.state = GameState.GAME_OVER

            # 检查是否到达终点
            player_rect = self.player.rect
            end_rect = pygame.Rect(*self.level.end_pos, 40, 40)

            if player_rect.colliderect(end_rect):
                # 计算得分
                time_bonus = max(0, 30000 - self.current_time) // 100
                health_bonus = int(self.player.health * 10)
                self.score = time_bonus + health_bonus
                print(f"玩家到达终点！设置状态为VICTORY，得分: {self.score}")
                self.state = GameState.VICTORY

    def draw_ui(self):
        """绘制游戏界面"""
        # UI背景
        ui_rect = pygame.Rect(GAME_WIDTH, 0, UI_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self.screen, (50, 50, 50), ui_rect)

        y_offset = 20  # 垂直间距，保证字不重叠

        # 关卡信息
        level_text = self.small_font.render(f"关卡: {self.current_level_num}", True, WHITE)
        self.screen.blit(level_text, (GAME_WIDTH + 10, y_offset))
        y_offset += 30

        # 时间
        time_seconds = self.current_time // 1000
        time_text = self.small_font.render(f"时间: {time_seconds}s", True, WHITE)
        self.screen.blit(time_text, (GAME_WIDTH + 10, y_offset))
        y_offset += 30

        # 血量
        if self.player:
            health_text = self.small_font.render(f"血量: {int(self.player.health)}", True, WHITE)
            self.screen.blit(health_text, (GAME_WIDTH + 10, y_offset))
            y_offset += 50

        # 图例
        legend_text = self.small_font.render("图例:", True, WHITE)
        self.screen.blit(legend_text, (GAME_WIDTH + 10, y_offset))
        y_offset += 25

        legends = [

            ("起点", GREEN),
            ("终点", YELLOW),
            ("墙壁", GRAY),
            ("沼泽", DARK_GREEN),
            ("陷阱", RED),

        ]

        for text, color in legends:
            pygame.draw.rect(self.screen, color, (GAME_WIDTH + 10, y_offset, 15, 15))
            label = self.small_font.render(text, True, WHITE)
            self.screen.blit(label, (GAME_WIDTH + 30, y_offset))
            y_offset += 20

        # 控制说明
        y_offset += 20
        controls_text = self.small_font.render("控制:", True, WHITE)
        self.screen.blit(controls_text, (GAME_WIDTH + 10, y_offset))
        y_offset += 25

        control_instructions = ["WASD移动", "ESC返回菜单", "+ 增大音量", "- 减小音量", "Tab 更换音乐", "0 静音"]
        for instruction in control_instructions:
            text = self.tiny_font.render(instruction, True, WHITE)
            self.screen.blit(text, (GAME_WIDTH + 10, y_offset))
            y_offset += 18

        y_offset += 25
        music = self.current_music_index
        controls_text = self.small_font.render("当前音乐:", True, WHITE)
        self.screen.blit(controls_text, (GAME_WIDTH + 10, y_offset))
        y_offset += 30
        controls_text = self.tiny_font.render(f"{self.name_list[music]}", True, WHITE)
        self.screen.blit(controls_text, (GAME_WIDTH + 10, y_offset))
        y_offset += 25
        controls_text = self.tiny_font.render(f"({self.owner_list[music]})", True, WHITE)
        self.screen.blit(controls_text, (GAME_WIDTH + 10, y_offset))

    def draw_menu(self):
        """绘制增强版主菜单，包含背景图片和动画元素"""
        # 加载背景图片（假设已在__init__中加载）
        background = pygame.transform.scale(self.background_img, (WINDOW_WIDTH, WINDOW_HEIGHT))
        self.screen.blit(background, (0, 0))

        # 绘制半透明遮罩，降低背景对比度
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        self.screen.blit(overlay, (0, 0))

        # 绘制标题文字和阴影
        title_text = "澎菲躲耄耄"
        title_shadow = self.huge_font.render(title_text, True, (30, 30, 30))
        title = self.huge_font.render(title_text, True, (255, 255, 255))

        # 多层阴影实现发光效果
        for offset in [(-3, -3), (3, -3), (-3, 3), (3, 3)]:
            self.screen.blit(title_shadow, (WINDOW_WIDTH // 2 - title.get_width() // 2 + offset[0], 135 + offset[1]))

        self.screen.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 135))

        # 菜单选项数据
        menu_options = [
            {"key": "1", "text": "开始关卡1", "action": "start_level_1"},
            {"key": "2", "text": "开始关卡2", "action": "start_level_2"},
            {"key": "R", "text": "开始随机关卡", "action": "start_random"},
            {"key": "Q", "text": "退出游戏", "action": "quit_game"}
        ]

        # 绘制菜单选项（分层设计）
        for i, option in enumerate(menu_options):
            base_y = 300 + i * 80

            # 计算鼠标悬停效果
            option_rect = pygame.Rect(WINDOW_WIDTH // 2 - 150, base_y, 300, 50)
            is_hovered = option_rect.collidepoint(pygame.mouse.get_pos())

            # 绘制底层阴影
            shadow_rect = option_rect.inflate(10, 10)
            shadow_rect.y += 5
            pygame.draw.rect(self.screen, (0, 0, 0, 80), shadow_rect, border_radius=12)

            # 绘制卡片背景（分层效果）
            card_back = option_rect.inflate(6, 6)
            card_back.y += 3
            pygame.draw.rect(self.screen, (50, 50, 70), card_back, border_radius=10)

            # 绘制主卡片
            if is_hovered:
                pygame.draw.rect(self.screen, (70, 70, 95), option_rect, border_radius=8)
                # 顶部高光
                pygame.draw.line(self.screen, (120, 120, 150),
                                 (option_rect.x + 5, option_rect.y + 2),
                                 (option_rect.right - 5, option_rect.y + 2), 2)
            else:
                pygame.draw.rect(self.screen, (60, 60, 85), option_rect, border_radius=8)

            # 绘制按键提示（3D效果）
            key_bg_rect = pygame.Rect(WINDOW_WIDTH // 2 - 140, base_y + 5, 40, 40)

            # 按钮底部
            pygame.draw.circle(self.screen, (120, 20, 20), key_bg_rect.center, 20)
            # 按钮顶部
            pygame.draw.circle(self.screen, (180, 30, 30), key_bg_rect.center, 18)
            # 高光
            pygame.draw.circle(self.screen, (255, 255, 255, 80),
                               (key_bg_rect.centerx - 5, key_bg_rect.centery - 5), 6)

            key_text = self.big_font.render(option["key"], True, (255, 255, 255))
            key_text_rect = key_text.get_rect(center=key_bg_rect.center)
            self.screen.blit(key_text, key_text_rect)

            # 绘制选项文本
            text = self.big_font.render(option["text"], True, (240, 240, 255))
            text_rect = text.get_rect(midleft=(WINDOW_WIDTH // 2 - 90, base_y + 25))

            # 添加文本阴影
            shadow_text = self.big_font.render(option["text"], True, (0, 0, 0, 100))
            self.screen.blit(shadow_text, (text_rect.x + 2, text_rect.y + 2))
            self.screen.blit(text, text_rect)

        animation_y = WINDOW_HEIGHT - 100  # 动画垂直位置（屏幕下方）
        animation_speed = 2  # 移动速度（像素/帧）

        # 更新位置（循环滚动）
        self.animation_positions["player"] += animation_speed
        self.animation_positions["enemy"] += animation_speed  # 敌人速度比玩家快，实现追逐效果

        # 玩家图片绘制
        player_x = self.animation_positions["player"]
        if player_x < WINDOW_WIDTH:
            # 绘制玩家图片
            self.screen.blit(self.player_img, (player_x, animation_y - 40))

        # 重置位置：当图片完全离开屏幕右侧时，回到左侧外
        if player_x > WINDOW_WIDTH + self.player_img.get_width():
            self.animation_positions["player"] = -self.player_img.get_width()

        # 敌人图片绘制
        enemy_x = self.animation_positions["enemy"]
        if enemy_x < WINDOW_WIDTH:
            # 绘制敌人图片（不翻转，默认面向右侧）
            self.screen.blit(self.enemy_img, (enemy_x, animation_y))

        # 重置位置：当图片完全离开屏幕右侧时，回到更左侧的位置（保持追逐逻辑）
        if enemy_x > WINDOW_WIDTH + self.enemy_img.get_width():
            self.animation_positions["enemy"] = -self.enemy_img.get_width()

    def draw_game_over(self):
        """绘制游戏结束画面"""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        game_over_text = self.huge_font.render("游戏结束!", True, RED)
        text_rect = game_over_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 80))
        self.screen.blit(game_over_text, text_rect)

        # 添加状态显示
        # state_text = self.big_font.render(f"当前状态: {self.state}", True, WHITE)
        # state_rect = state_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 40))
        # self.screen.blit(state_text, state_rect)

        restart_text = self.big_font.render("按 R 重新开始", True, WHITE)
        restart_rect = restart_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        self.screen.blit(restart_text, restart_rect)

        menu_text = self.big_font.render("按 M 或 ESC 返回菜单", True, WHITE)
        menu_rect = menu_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 60))
        self.screen.blit(menu_text, menu_rect)

    def draw_victory(self):
        """绘制胜利画面"""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(BLACK)
        self.screen.blit(overlay, (0, 0))

        victory_text = self.huge_font.render("恭喜通关!", True, GREEN)
        text_rect = victory_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 100))
        self.screen.blit(victory_text, text_rect)

        # 添加状态显示
        # state_text = self.big_font.render(f"当前状态: {self.state}", True, WHITE)
        # state_rect = state_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 60))
        # self.screen.blit(state_text, state_rect)

        score_text = self.big_font.render(f"得分: {self.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 - 20))
        self.screen.blit(score_text, score_rect)

        time_text = self.big_font.render(f"用时: {self.current_time // 1000}秒", True, WHITE)
        time_rect = time_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 30))
        self.screen.blit(time_text, time_rect)

        next_text = self.big_font.render("按 N 或 空格键 下一关", True, WHITE)
        next_rect = next_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 80))
        self.screen.blit(next_text, next_rect)

        menu_text = self.big_font.render("按 M 或 ESC 返回菜单", True, WHITE)
        menu_rect = menu_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2 + 130))
        self.screen.blit(menu_text, menu_rect)

    def run(self):
        """主游戏循环"""
        running = True

        while running:
            # 清空屏幕
            self.screen.fill(BLACK)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:  # 用户关闭了窗口
                    running = False

                elif event.type == pygame.KEYDOWN:  # 用户按键
                    key_name = pygame.key.name(event.key)
                    print(f"检测到按键: {key_name}, 当前状态: {self.state}")

                    if self.state == GameState.MENU:
                        if event.key == pygame.K_1:
                            print("开始关卡1")
                            self.start_level(1)
                        elif event.key == pygame.K_2:
                            print("开始关卡2")
                            self.start_level(2)
                        elif event.key == pygame.K_r:
                            print("开始随机关卡")
                            self.start_level(999)  # 随机关卡
                        elif event.key == pygame.K_q:
                            print("退出游戏")
                            running = False

                    elif self.state == GameState.PLAYING:
                        if event.key == pygame.K_ESCAPE:
                            print("返回主菜单")
                            self.state = GameState.MENU

                        elif event.key == pygame.K_TAB:  # 切换音乐
                            self.current_music_index = (self.current_music_index + 1) % len(self.music_list)
                            self.load_music(self.current_music_index)  # 加载并播放新音乐
                            print(f"切换到音乐: {self.music_list[self.current_music_index]}")

                        elif event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS:  # 增大音量 (+ 键)
                            self.volume = min(1.0, self.volume + self.volume_step)
                            pygame.mixer.music.set_volume(self.volume)
                            print(f"音量增大到: {self.volume:.1f}")

                        elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:  # 减小音量 (- 键)
                            self.volume = max(0.0, self.volume - self.volume_step)
                            pygame.mixer.music.set_volume(self.volume)
                            print(f"音量减小到: {self.volume:.1f}")

                        elif event.key == pygame.K_0:  # 静音/取消静音
                            if self.volume > 0:
                                self.last_volume = self.volume  # 保存当前音量
                                self.volume = 0
                                pygame.mixer.music.set_volume(0)
                                print("已静音")
                            else:
                                self.volume = self.last_volume if hasattr(self, 'last_volume') else 0.5
                                pygame.mixer.music.set_volume(self.volume)
                                print(f"已恢复音量: {self.volume:.1f}")



                    elif self.state == GameState.GAME_OVER:
                        print(f"游戏结束状态，按键: {key_name}")
                        if event.key == pygame.K_r:
                            print("重新开始关卡")
                            self.start_level(self.current_level_num)
                        elif event.key == pygame.K_m:
                            print("返回主菜单")
                            self.state = GameState.MENU
                        elif event.key == pygame.K_ESCAPE:
                            print("ESC返回主菜单")
                            self.state = GameState.MENU

                    elif self.state == GameState.VICTORY:
                        print(f"胜利状态，按键: {key_name}")
                        if event.key == pygame.K_n or event.key == pygame.K_SPACE:
                            print("进入下一关")
                            self.start_level(self.current_level_num + 1)
                        elif event.key == pygame.K_m or event.key == pygame.K_ESCAPE:
                            print("返回主菜单")
                            self.state = GameState.MENU

            # 处理输入
            self.handle_input()

            # 更新游戏状态
            self.update()

            # 绘制
            if self.state == GameState.MENU:
                self.draw_menu()
            elif self.state in [GameState.PLAYING, GameState.GAME_OVER, GameState.VICTORY]:
                # 绘制游戏区域背景
                game_area = pygame.Rect(0, 0, GAME_WIDTH, GAME_HEIGHT)
                pygame.draw.rect(self.screen, WHITE, game_area)

                # 绘制关卡
                if self.level:
                    self.level.draw(self.screen)

                # 绘制玩家
                if self.player:
                    self.player.draw(self.screen)

                # 绘制游戏区域边界
                pygame.draw.rect(self.screen, BLACK, game_area, 2)

                # 绘制UI
                self.draw_ui()

                # 绘制覆盖层
                if self.state == GameState.GAME_OVER:
                    self.draw_game_over()
                elif self.state == GameState.VICTORY:
                    self.draw_victory()

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()

    def load_music(self, current_music_index):
        play_background_music(self.music_list[current_music_index])


# 示例JSON关卡文件格式
def save_example_level():
    """保存示例关卡到JSON文件"""
    example_level = {
        "start": [20, 20],
        "end": [700, 500],
        "obstacles": [
            {
                "x": 200,
                "y": 100,
                "width": 20,
                "height": 200,
                "type": 1,
                "description": "wall"
            },
            {
                "x": 300,
                "y": 300,
                "width": 80,
                "height": 80,
                "type": 2,
                "description": "swamp"
            },
            {
                "x": 500,
                "y": 100,
                "width": 30,
                "height": 30,
                "type": 3,
                "description": "trap"
            },
            {
                "x": 600,
                "y": 300,
                "width": ENEMY_WIDTH,
                "height": ENEMY_HEIGHT,
                "type": 4,
                "description": "enemy",
                "path": [[600, 300], [650, 300], [650, 350], [600, 350]]
            }
        ]
    }
    with open('example_level.json', 'w', encoding='utf-8') as f:
        json.dump(example_level, f, indent=2, ensure_ascii=False)


def enhance_color_saturation(image, factor=1.5):
    enhanced_image = image.copy()
    width, height = enhanced_image.get_size()

    # 遍历每个像素并调整饱和度
    for x in range(width):
        for y in range(height):
            # 获取像素颜色和透明度
            color = enhanced_image.get_at((x, y))
            alpha = color[3]

            # 跳过完全透明的像素
            if alpha == 0:
                continue

            # 计算亮度（灰度值）
            luminance = int(0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2])

            # 调整饱和度
            r = int(luminance + factor * (color[0] - luminance))
            g = int(luminance + factor * (color[1] - luminance))
            b = int(luminance + factor * (color[2] - luminance))

            # 确保颜色值在有效范围内
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            # 应用调整后的颜色（保留原始透明度）
            enhanced_image.set_at((x, y), (r, g, b, alpha))
    return enhanced_image


if __name__ == "__main__":
    # 保存示例关卡文件
    save_example_level()
    play_background_music('music/哈基米大冒险.mp3', -1, 0.5)
    # 启动游戏
    game = Game()
    game.run()
