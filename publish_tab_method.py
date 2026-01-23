    def create_publish_tab(self):
        """Create Publish tab for staging, release, and automation"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Info section
        info = QLabel("<b>Publish & Release</b> — Stage photos for platforms, automate uploads, and track release status.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Staging section
        staging_group = QFrame()
        staging_group.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        staging_layout = QVBoxLayout(staging_group)
        
        staging_label = QLabel("<b>Stage for Platforms</b>")
        staging_layout.addWidget(staging_label)
        
        staging_controls = QHBoxLayout()
        staging_controls.addWidget(QLabel("Stage selected photos to:"))
        
        stage_ig = QPushButton()
        stage_ig.setIcon(self.get_icon("instagram.png", "IG"))
        stage_ig.setIconSize(self.icon_size)
        stage_ig.setToolTip("Stage to Instagram")
        stage_ig.clicked.connect(lambda: self.toggle_staged("instagram"))
        staging_controls.addWidget(stage_ig)
        
        stage_tt = QPushButton()
        stage_tt.setIcon(self.get_icon("tiktok.png", "TT"))
        stage_tt.setIconSize(self.icon_size)
        stage_tt.setToolTip("Stage to TikTok")
        stage_tt.clicked.connect(lambda: self.toggle_staged("tiktok"))
        staging_controls.addWidget(stage_tt)
        
        stage_f = QPushButton()
        stage_f.setIcon(self.get_icon("fansly.png", "F"))
        stage_f.setIconSize(self.icon_size)
        stage_f.setToolTip("Stage to Fansly")
        stage_f.clicked.connect(lambda: self.toggle_staged("fansly"))
        staging_controls.addWidget(stage_f)
        
        staging_controls.addStretch()
        staging_layout.addLayout(staging_controls)
        
        layout.addWidget(staging_group)
        
        # Release section
        release_group = QFrame()
        release_group.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        release_layout = QVBoxLayout(release_group)
        
        release_label = QLabel("<b>Release to Platforms</b>")
        release_layout.addWidget(release_label)
        
        release_controls = QHBoxLayout()
        release_controls.addWidget(QLabel("Release selected photos to:"))
        
        rel_ig = QPushButton()
        rel_ig.setIcon(self.get_icon("instagram.png", "IG"))
        rel_ig.setIconSize(self.icon_size)
        rel_ig.setToolTip("Release: Instagram")
        rel_ig.clicked.connect(lambda: self.toggle_release_status("released_instagram"))
        release_controls.addWidget(rel_ig)
        
        rel_tt = QPushButton()
        rel_tt.setIcon(self.get_icon("tiktok.png", "TT"))
        rel_tt.setIconSize(self.icon_size)
        rel_tt.setToolTip("Release: TikTok")
        rel_tt.clicked.connect(lambda: self.toggle_release_status("released_tiktok"))
        release_controls.addWidget(rel_tt)
        
        rel_f = QPushButton()
        rel_f.setIcon(self.get_icon("fansly.png", "F"))
        rel_f.setIconSize(self.icon_size)
        rel_f.setToolTip("Release: Fansly")
        rel_f.clicked.connect(lambda: self.toggle_release_status("released_fansly"))
        release_controls.addWidget(rel_f)
        
        release_controls.addStretch()
        release_layout.addLayout(release_controls)
        
        layout.addWidget(release_group)
        
        # Manage section
        manage_group = QFrame()
        manage_group.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        manage_layout = QVBoxLayout(manage_group)
        
        manage_label = QLabel("<b>Manage</b>")
        manage_layout.addWidget(manage_label)
        
        manage_controls = QHBoxLayout()
        
        unstage_btn = QPushButton()
        unstage_btn.setIcon(self.get_icon("unstage.png", "US"))
        unstage_btn.setIconSize(self.icon_size)
        unstage_btn.setToolTip("Unstage: move back to root/<package>")
        unstage_btn.clicked.connect(self.unstage_selected)
        manage_controls.addWidget(unstage_btn)
        
        pkg_btn = QPushButton()
        pkg_btn.setIcon(self.get_icon("package.png", "PK"))
        pkg_btn.setIconSize(self.icon_size)
        pkg_btn.setToolTip("Manage packages")
        pkg_btn.clicked.connect(self.manage_packages_dialog)
        manage_controls.addWidget(pkg_btn)
        
        unpkg_btn = QPushButton()
        unpkg_btn.setIcon(self.get_icon("unpackage.png", "UP"))
        unpkg_btn.setIconSize(self.icon_size)
        unpkg_btn.setToolTip("Unpackage: clear package and move to root")
        unpkg_btn.clicked.connect(self.unpackage_selected)
        manage_controls.addWidget(unpkg_btn)
        
        manage_controls.addStretch()
        manage_layout.addLayout(manage_controls)
        
        layout.addWidget(manage_group)
        
        # Placeholder for future: automation, scheduling, upload logs
        layout.addStretch()
        
        coming_soon = QLabel("<i>Coming soon: Automated uploads, scheduling, caption templates, upload history</i>")
        coming_soon.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(coming_soon)
        
        return widget
